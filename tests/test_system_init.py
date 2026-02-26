"""
Offline integration tests for SystemInitializer.

Verifies all six INIT requirements without a running game, FalkorDB, or
any external service.

Requirements covered:
  INIT-01 (test_init_rejects_missing_config_file, test_init_rejects_invalid_config,
            test_init_rejects_missing_frame_duration)
  INIT-02 (test_init_loads_prior_knowledge)
  INIT-03 (test_init_runs_discovery_without_prior)
  INIT-04 (test_init_skips_experimentation_with_prior)
  INIT-05 (test_init_prints_status_messages)
  INIT-06 (test_init_rejects_missing_frame_duration,
            test_init_frame_duration_from_config)
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from control.system_initializer import SystemInitializer, InitializationResult


# =============================================================================
# HELPERS
# =============================================================================


class MockAdapter:
    """Fake adapter for offline testing.

    Has wait_one_tick() so SystemInitializer uses it instead of time.sleep.
    """

    def __init__(self):
        self._connected = True
        self._tick = 0
        self._speed = 50.0

    def connect(self, **kwargs):
        return True

    def is_connected(self):
        return self._connected

    def get_feedbacks(self):
        return {
            'speed':    self._speed,
            'pos_x':    0.0,
            'pos_y':    0.0,
            'pos_z':    0.0,
            'yaw':      0.0,
            'race_time': float(self._tick * 10),
        }

    def send_action_dict(self, action):
        # Simulate: gas increases speed, brake decreases
        if action.get('gas', 0) > 0:
            self._speed += 5.0
        if action.get('brake', 0) > 0:
            self._speed -= 3.0
        return True

    def wait_one_tick(self):
        self._tick += 1

    def save_state(self):
        return True

    def rewind(self):
        return True

    def stop(self):
        pass


def make_test_config(tmp_path, frame_duration_ms=10, results_dir=None,
                     include_timing=True):
    """Create a valid TMNF config JSON file in tmp_path.

    Args:
        tmp_path: pytest tmp_path fixture.
        frame_duration_ms: value for environment.timing.frame_duration_ms.
        results_dir: override prior_knowledge.results_dir (defaults to tmp_path).
        include_timing: if False, omit environment.timing entirely (for INIT-06 tests).
    """
    config: dict = {
        "system_name": "test",
        "version": "1.0.0",
        "actions": {
            "gas":      {"type": "binary", "range": [0.0, 1.0]},
            "brake":    {"type": "binary", "range": [0.0, 1.0]},
            "steering": {"type": "analog",  "range": [-1.0, 1.0]},
        },
        "feedbacks": {
            "speed": {
                "description":  "speed",
                "unit":         "km/h",
                "interval_size": 5.0,
                "expected_range": [0.0, 500.0],
            }
        },
        "environment": {
            "type": "tmnf",
            "host": "127.0.0.1",
            "port": 8476,
        },
        "prior_knowledge": {
            "check_on_startup": True,
            "results_dir":     str(results_dir or tmp_path),
            "results_pattern": "tmnf_phase_a_results_*.json",
        },
        "experimentation": {
            "enabled":           True,
            "search_precision":  0.001,
            "min_probe_speed_kmh": 10.0,
            "use_rewind":        True,
        },
    }

    if include_timing:
        config["environment"]["timing"] = {"frame_duration_ms": frame_duration_ms}

    config_path = tmp_path / "test_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return str(config_path)


def make_fake_prior_knowledge(results_dir):
    """Write a fake tmnf_phase_a_results_*.json file in results_dir.

    Returns the path to the created file.
    """
    data = {
        "timestamp": "20260225_150000",
        "environment": "TMNF",
        "results": {
            "gas": {
                "max": 1.0,
                "min": 0.001,
                "bins": 2,
                "delta_max": 5.0,
                "delta_0": 0.0,
                "input_type": "binary",
                "bin_details": [
                    {"id": 0, "min": 0.0, "max": 0.001, "label": "DEAD_ZONE"},
                    {"id": 1, "min": 0.001, "max": 1.0,  "label": "ON"},
                ],
            },
            "brake": {
                "max": 1.0,
                "min": 0.001,
                "bins": 2,
                "delta_max": -3.0,
                "delta_0": 0.0,
                "input_type": "binary",
                "bin_details": [
                    {"id": 0, "min": 0.0, "max": 0.001, "label": "DEAD_ZONE"},
                    {"id": 1, "min": 0.001, "max": 1.0,  "label": "ON"},
                ],
            },
            "steering": {
                "max": 1.0,
                "min": 0.01,
                "bins": 201,
                "delta_max": 0.05,
                "delta_0": 0.0,
                "input_type": "analog",
                "precision": 0.005,
                "bin_details": [
                    {"id": 0, "min": -0.01, "max": 0.01, "label": "STRAIGHT"},
                    {"id": 1, "min":  0.01, "max": 0.02, "label": "RIGHT_BIN_1"},
                ],
            },
        },
    }
    path = os.path.join(str(results_dir), "tmnf_phase_a_results_20260225_150000.json")
    with open(path, 'w') as f:
        json.dump(data, f)
    return path


# =============================================================================
# INIT-01 TESTS: Bad config rejected
# =============================================================================


def test_init_rejects_missing_config_file(tmp_path):
    """INIT-01: System refuses to start when config file doesn't exist."""
    nonexistent = str(tmp_path / "does_not_exist.json")
    init = SystemInitializer(config_path=nonexistent)
    result = init.initialize()

    assert result.success is False
    assert any("Config file not found" in e or "not found" in e.lower()
               for e in result.errors), \
        f"Expected 'file not found' error but got: {result.errors}"


def test_init_rejects_invalid_json(tmp_path):
    """INIT-01: System refuses to start when config is not valid JSON."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ this is not valid json !!!")
    init = SystemInitializer(config_path=str(bad_json))
    result = init.initialize()

    assert result.success is False
    assert any("Invalid JSON" in e or "json" in e.lower()
               for e in result.errors), \
        f"Expected JSON error but got: {result.errors}"


def test_init_rejects_invalid_config(tmp_path):
    """INIT-01: System refuses to start when config is semantically invalid.

    Config is valid JSON but missing required keys (no actions).
    """
    bad_config = {
        "system_name": "test",
        "version": "1.0.0",
        # Missing 'actions', 'feedbacks', 'environment'
    }
    cfg_path = tmp_path / "bad_config.json"
    cfg_path.write_text(json.dumps(bad_config))
    init = SystemInitializer(config_path=str(cfg_path))
    result = init.initialize()

    assert result.success is False
    assert result.errors, "Expected at least one error for invalid config"


# =============================================================================
# INIT-06 TEST: frame_duration_ms must come from config
# =============================================================================


def test_init_rejects_missing_frame_duration(tmp_path):
    """INIT-06: System refuses to start when frame_duration_ms is missing.

    Sutton Jan 24: frame duration must be configured, not hard-coded.
    """
    config_path = make_test_config(tmp_path, include_timing=False)
    init = SystemInitializer(config_path=config_path)
    result = init.initialize()

    assert result.success is False
    assert result.errors, "Expected validation error for missing frame_duration_ms"


# =============================================================================
# INIT-02 / INIT-04 TESTS: Prior knowledge detection and loading
# =============================================================================


def test_init_loads_prior_knowledge(tmp_path):
    """INIT-02: System detects and loads existing bin discovery results.

    INIT-04: When prior knowledge exists, experimentation is skipped.
    No adapter connection attempted.
    """
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, results_dir=tmp_path)

    init = SystemInitializer(config_path=config_path)
    result = init.initialize()

    assert result.success is True, \
        f"Expected success with prior knowledge but got errors: {result.errors}"
    assert result.has_prior_knowledge is True, \
        "Expected has_prior_knowledge=True"
    assert result.bins_acquired, \
        "Expected bins_acquired to be non-empty"
    assert 'gas' in result.bins_acquired, \
        "Expected 'gas' action in bins_acquired"


def test_init_skips_experimentation_with_prior(tmp_path):
    """INIT-04: When prior knowledge exists, bin acquisition stage is SKIPPED.

    Sutton: 'when there is previous knowledge... no need to validate anything'
    """
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, results_dir=tmp_path)

    init = SystemInitializer(config_path=config_path)
    result = init.initialize()

    from control.system_initializer import InitializationStatus
    assert result.stages.get('bin_acquisition') == InitializationStatus.SKIPPED, \
        f"Expected bin_acquisition=SKIPPED but got: {result.stages.get('bin_acquisition')}"
    assert result.stages.get('adapter_connect') == InitializationStatus.SKIPPED, \
        f"Expected adapter_connect=SKIPPED but got: {result.stages.get('adapter_connect')}"


# =============================================================================
# INIT-03 TEST: Bin discovery runs when no prior knowledge
# =============================================================================


def test_init_runs_discovery_without_prior(tmp_path):
    """INIT-03: System runs bin discovery when no prior knowledge exists.

    Tests WIRING: patches ExperimentationCoordinator (via control.system_initializer
    import path) so we verify SystemInitializer calls it, without running the real
    algorithm (which needs a live game).
    """
    # Empty results dir -- no prior knowledge
    config_path = make_test_config(tmp_path, results_dir=tmp_path)
    mock_adapter = MockAdapter()

    from intelligence.intelligence_experimentation import ActionDiscoveryResult

    def make_fake_result(name):
        r = ActionDiscoveryResult(action_name=name)
        r.success = True
        r.a_min_effective = 0.001
        r.a_max_effective = 1.0
        return r

    fake_bins = {
        'gas':   [{'bin_id': 0, 'min': 0.0,   'max': 0.001, 'label': 'DEAD_ZONE',
                   'effect_delta': 0.0},
                  {'bin_id': 1, 'min': 0.001, 'max': 1.0,   'label': 'ON',
                   'effect_delta': 5.0}],
        'brake': [{'bin_id': 0, 'min': 0.0,   'max': 0.001, 'label': 'DEAD_ZONE',
                   'effect_delta': 0.0},
                  {'bin_id': 1, 'min': 0.001, 'max': 1.0,   'label': 'ON',
                   'effect_delta': -3.0}],
    }

    # Build a mock coordinator whose run_full_experimentation returns fake_bins
    # and whose .intelligence.discovery_results has ActionDiscoveryResult objects.
    mock_coordinator = MagicMock()
    mock_coordinator.run_full_experimentation.return_value = fake_bins
    mock_coordinator.intelligence.discovery_results = {
        'gas':   make_fake_result('gas'),
        'brake': make_fake_result('brake'),
    }

    # Patch ExperimentationCoordinator where it's imported inside _acquire_bins
    with patch(
        'intelligence.intelligence_experimentation.ExperimentationCoordinator',
        return_value=mock_coordinator,
    ) as MockCoordinatorClass:
        init = SystemInitializer(config_path=config_path, adapter=mock_adapter)
        result = init.initialize()

    # Verify the coordinator was instantiated and discovery was called
    MockCoordinatorClass.assert_called_once()
    mock_coordinator.run_full_experimentation.assert_called_once()

    assert result.success is True, \
        f"Expected success after discovery but got errors: {result.errors}"
    assert result.has_prior_knowledge is False, \
        "Expected has_prior_knowledge=False (bins came from discovery, not prior)"


# =============================================================================
# INIT-05 TEST: Status messages printed
# =============================================================================


def test_init_prints_status_messages(capsys, tmp_path):
    """INIT-05: System prints status at each startup stage.

    Sutton: 'you can print everything to screen like validation started,
    bins acquired'
    """
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, results_dir=tmp_path)

    init = SystemInitializer(config_path=config_path)
    init.initialize()

    captured = capsys.readouterr()
    output = captured.out

    assert "SYSTEM INITIALIZATION" in output, \
        "Expected 'SYSTEM INITIALIZATION' in output"
    assert "Config" in output, \
        "Expected config status message in output"
    assert "Prior knowledge" in output, \
        "Expected prior knowledge status message in output"
    assert "SYSTEM READY" in output, \
        "Expected 'SYSTEM READY' final status in output"


# =============================================================================
# INIT-06 TEST: frame_duration_ms from config
# =============================================================================


def test_init_frame_duration_from_config(tmp_path):
    """INIT-06: frame_duration_ms is read from config, not hardcoded.

    Sutton Jan 24: 'this needs to be determined by the system so it's being
    configured not hard-coded'
    """
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, frame_duration_ms=10,
                                   results_dir=tmp_path)

    init = SystemInitializer(config_path=config_path)
    result = init.initialize()

    assert result.success is True
    assert result.frame_duration_ms == 10.0, \
        f"Expected frame_duration_ms=10.0 but got {result.frame_duration_ms}"
