"""
Offline integration tests for SystemInitializer.

Verifies all six INIT requirements without a running game, FalkorDB, or
any external service.

Requirements covered:
  INIT-01 (test_init_rejects_missing_config_file, test_init_rejects_invalid_config)
  INIT-02 (test_init_detects_prior_knowledge)
  INIT-03 (test_init_runs_discovery_without_prior)
  INIT-04 (test_init_user_accepts_prior_knowledge, test_init_user_declines_prior_knowledge)
  INIT-05 (test_init_prints_status_messages)
  INIT-06 (test_init_discovers_frame_duration_from_adapter)
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

    Simulates TMNF adapter with race_time that advances 10ms per tick
    (so frame duration discovery measures 10ms).
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
            'speed':     self._speed,
            'pos_x':     0.0,
            'pos_y':     0.0,
            'pos_z':     0.0,
            'yaw':       0.0,
            'race_time': float(self._tick * 10),
        }

    def send_action_dict(self, action):
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


def make_test_config(tmp_path, results_dir=None):
    """Create a valid TMNF config JSON file in tmp_path.

    No frame_duration_ms — it's discovered from environment, not config.
    """
    config = {
        "system_name": "test",
        "version": "1.0.0",
        "actions": {
            "gas":      {"type": "binary", "range": [0.0, 1.0]},
            "brake":    {"type": "binary", "range": [0.0, 1.0]},
            "steering": {"type": "analog",  "range": [-1.0, 1.0]},
        },
        "feedbacks": {
            "speed": {
                "description":   "speed",
                "unit":          "km/h",
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
            "results_dir":      str(results_dir or tmp_path),
            "results_pattern":  "tmnf_phase_a_results_*.json",
        },
        "experimentation": {
            "enabled":            True,
            "search_precision":   0.001,
            "min_probe_speed_kmh": 10.0,
            "use_rewind":         True,
        },
    }

    config_path = tmp_path / "test_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return str(config_path)


def make_fake_prior_knowledge(results_dir):
    """Write a fake tmnf_phase_a_results_*.json file in results_dir."""
    data = {
        "timestamp": "20260225_150000",
        "environment": "TMNF",
        "results": {
            "gas": {
                "max": 1.0, "min": 0.001, "bins": 2,
                "delta_max": 5.0, "delta_0": 0.0, "input_type": "binary",
                "bin_details": [
                    {"id": 0, "min": 0.0, "max": 0.001, "label": "DEAD_ZONE"},
                    {"id": 1, "min": 0.001, "max": 1.0,  "label": "ON"},
                ],
            },
            "brake": {
                "max": 1.0, "min": 0.001, "bins": 2,
                "delta_max": -3.0, "delta_0": 0.0, "input_type": "binary",
                "bin_details": [
                    {"id": 0, "min": 0.0, "max": 0.001, "label": "DEAD_ZONE"},
                    {"id": 1, "min": 0.001, "max": 1.0,  "label": "ON"},
                ],
            },
            "steering": {
                "max": 1.0, "min": 0.01, "bins": 201,
                "delta_max": 0.05, "delta_0": 0.0, "input_type": "analog",
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
    assert any("not found" in e.lower() for e in result.errors)


def test_init_rejects_invalid_json(tmp_path):
    """INIT-01: System refuses to start when config is not valid JSON."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ this is not valid json !!!")
    init = SystemInitializer(config_path=str(bad_json))
    result = init.initialize()

    assert result.success is False
    assert any("json" in e.lower() for e in result.errors)


def test_init_rejects_invalid_config(tmp_path):
    """INIT-01: System refuses to start when config is semantically invalid."""
    bad_config = {"system_name": "test", "version": "1.0.0"}
    cfg_path = tmp_path / "bad_config.json"
    cfg_path.write_text(json.dumps(bad_config))
    init = SystemInitializer(config_path=str(cfg_path))
    result = init.initialize()

    assert result.success is False
    assert result.errors


# =============================================================================
# INIT-02 / INIT-04 TESTS: Prior knowledge — user choice
# =============================================================================


def test_init_user_accepts_prior_knowledge(tmp_path):
    """INIT-02 + INIT-04: Prior knowledge found, user says yes.

    System loads bins, skips experimentation.
    """
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, results_dir=tmp_path)

    # User says "y" — use prior knowledge
    # Adapter still needed for frame duration discovery
    mock_adapter = MockAdapter()
    init = SystemInitializer(
        config_path=config_path,
        adapter=mock_adapter,
        user_input_fn=lambda prompt: "y",
    )
    result = init.initialize()

    assert result.success is True
    assert result.has_prior_knowledge is True
    assert 'gas' in result.bins_acquired
    assert result.bins_acquired['gas']['bins'] == 2

    from control.system_initializer import InitializationStatus
    assert result.stages['bin_acquisition'] == InitializationStatus.SKIPPED


def test_init_user_declines_prior_knowledge(tmp_path):
    """INIT-04: Prior knowledge found, user says no.

    System re-runs experimentation (mocked).
    """
    make_fake_prior_knowledge(tmp_path)
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
        'gas':   [{'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE',
                   'effect_delta': 0.0},
                  {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON',
                   'effect_delta': 5.0}],
    }

    mock_coordinator = MagicMock()
    mock_coordinator.run_full_experimentation.return_value = fake_bins
    mock_coordinator.intelligence.discovery_results = {
        'gas': make_fake_result('gas'),
    }

    # User says "n" — re-run experimentation
    with patch(
        'intelligence.intelligence_experimentation.ExperimentationCoordinator',
        return_value=mock_coordinator,
    ):
        init = SystemInitializer(
            config_path=config_path,
            adapter=mock_adapter,
            user_input_fn=lambda prompt: "n",
        )
        result = init.initialize()

    assert result.success is True
    assert result.has_prior_knowledge is False
    mock_coordinator.run_full_experimentation.assert_called_once()


def test_init_no_prior_knowledge_skips_question(tmp_path):
    """INIT-02: When no prior knowledge exists, user is NOT asked."""
    # Empty dir — no results files
    config_path = make_test_config(tmp_path, results_dir=tmp_path)
    mock_adapter = MockAdapter()

    # If user_input_fn is called, it means we asked when we shouldn't have
    asked = []

    def fail_if_asked(prompt):
        asked.append(prompt)
        return "y"

    from intelligence.intelligence_experimentation import ActionDiscoveryResult

    def make_fake_result(name):
        r = ActionDiscoveryResult(action_name=name)
        r.success = True
        r.a_min_effective = 0.001
        r.a_max_effective = 1.0
        return r

    mock_coordinator = MagicMock()
    mock_coordinator.run_full_experimentation.return_value = {
        'gas': [{'bin_id': 0, 'min': 0.0, 'max': 1.0, 'label': 'ON',
                 'effect_delta': 5.0}],
    }
    mock_coordinator.intelligence.discovery_results = {
        'gas': make_fake_result('gas'),
    }

    with patch(
        'intelligence.intelligence_experimentation.ExperimentationCoordinator',
        return_value=mock_coordinator,
    ):
        init = SystemInitializer(
            config_path=config_path,
            adapter=mock_adapter,
            user_input_fn=fail_if_asked,
        )
        result = init.initialize()

    assert result.success is True
    assert len(asked) == 0, f"User was asked even though no prior knowledge: {asked}"


# =============================================================================
# INIT-03 TEST: Bin discovery runs when no prior knowledge
# =============================================================================


def test_init_runs_discovery_without_prior(tmp_path):
    """INIT-03: System runs bin discovery when no prior knowledge exists."""
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
        'gas':   [{'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE',
                   'effect_delta': 0.0},
                  {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON',
                   'effect_delta': 5.0}],
        'brake': [{'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE',
                   'effect_delta': 0.0},
                  {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON',
                   'effect_delta': -3.0}],
    }

    mock_coordinator = MagicMock()
    mock_coordinator.run_full_experimentation.return_value = fake_bins
    mock_coordinator.intelligence.discovery_results = {
        'gas':   make_fake_result('gas'),
        'brake': make_fake_result('brake'),
    }

    with patch(
        'intelligence.intelligence_experimentation.ExperimentationCoordinator',
        return_value=mock_coordinator,
    ) as MockCoordinatorClass:
        init = SystemInitializer(config_path=config_path, adapter=mock_adapter)
        result = init.initialize()

    MockCoordinatorClass.assert_called_once()
    mock_coordinator.run_full_experimentation.assert_called_once()

    assert result.success is True
    assert result.has_prior_knowledge is False


# =============================================================================
# INIT-05 TEST: Status messages printed
# =============================================================================


def test_init_prints_status_messages(capsys, tmp_path):
    """INIT-05: System prints status at each startup stage."""
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, results_dir=tmp_path)
    mock_adapter = MockAdapter()

    init = SystemInitializer(
        config_path=config_path,
        adapter=mock_adapter,
        user_input_fn=lambda prompt: "y",
    )
    init.initialize()

    captured = capsys.readouterr()
    output = captured.out

    assert "SYSTEM INITIALIZATION" in output
    assert "Config" in output
    assert "Prior knowledge" in output
    assert "SYSTEM READY" in output


# =============================================================================
# INIT-06 TEST: Frame duration DISCOVERED from environment
# =============================================================================


def test_init_discovers_frame_duration_from_adapter(tmp_path):
    """INIT-06: Frame duration is discovered from environment, not hardcoded.

    Sutton: "who defines the time stamp is the environment"
    Sutton: "determined by the system so it's being configured not hard-coded"

    MockAdapter's race_time advances 10ms per tick, so discovery should
    measure 10ms.
    """
    make_fake_prior_knowledge(tmp_path)
    config_path = make_test_config(tmp_path, results_dir=tmp_path)
    mock_adapter = MockAdapter()

    init = SystemInitializer(
        config_path=config_path,
        adapter=mock_adapter,
        user_input_fn=lambda prompt: "y",
    )
    result = init.initialize()

    assert result.success is True
    assert result.frame_duration_ms == 10.0, \
        f"Expected 10ms (from MockAdapter race_time delta), got {result.frame_duration_ms}"

    from control.system_initializer import InitializationStatus
    assert result.stages['frame_duration_discovery'] == InitializationStatus.COMPLETED


def test_init_frame_duration_not_in_config(tmp_path):
    """INIT-06: Config does NOT contain frame_duration_ms — it's discovered."""
    config_path = make_test_config(tmp_path, results_dir=tmp_path)
    with open(config_path) as f:
        config = json.load(f)

    # Verify config has no frame_duration_ms anywhere
    env = config.get('environment', {})
    timing = env.get('timing', {})
    assert 'frame_duration_ms' not in timing, \
        "Config should NOT contain frame_duration_ms — it's discovered from environment"
    assert 'frame_duration_ms' not in env, \
        "Config should NOT contain frame_duration_ms"
