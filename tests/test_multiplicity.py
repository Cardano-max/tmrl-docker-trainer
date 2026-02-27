"""
Offline Tests for MultiplicityTester

Tests run WITHOUT TMNF/TMInterface -- uses MockMultiplicityAdapter
that simulates binary TMNF inputs.

Validates:
- GRAPH-12: Multiplicity testing (no linearity assumptions)
- Binary inputs have exactly 2 bins (DEAD_ZONE + ON), no intermediates
- Probe-rewind cycle is deterministic (speed returns to saved value)
- Delta matching with configurable tolerance
"""

import pytest
from intelligence.intelligence_experimentation import ActionBin
from intelligence.multiplicity_tester import (
    MultiplicityTester,
    MultiplicityResult,
    MultiplicityProbe,
)


# =============================================================================
# MOCK ADAPTER
# =============================================================================

class MockMultiplicityAdapter:
    """
    Simulates binary TMNF inputs for offline multiplicity testing.

    Behavior:
      - gas > 0.001 -> speed += 5.0 (binary, same delta for any value)
      - brake > 0.001 -> speed -= 3.0 (binary, same delta for any value)
      - left/right: no effect on speed (we test on speed)
      - gas/brake <= 0.001 -> no delta (dead zone)
    """

    def __init__(self):
        self.speed = 50.0
        self.saved_speed = 50.0
        self.last_action = {}
        self.rewind_count = 0
        self.save_count = 0

    def save_state(self):
        self.saved_speed = self.speed
        self.save_count += 1
        return True

    def rewind(self):
        self.speed = self.saved_speed
        self.rewind_count += 1
        return True

    def send_action_dict(self, action):
        self.last_action = action.copy()
        return True

    def wait_one_tick(self):
        # Binary behavior: any gas > 0.001 gives +5.0, any brake > 0.001 gives -3.0
        if self.last_action.get('gas', 0) > 0.001:
            self.speed += 5.0
        if self.last_action.get('brake', 0) > 0.001:
            self.speed = max(0, self.speed - 3.0)
        # Left/right: no effect on speed (tested via yaw in live)

    def get_feedbacks(self):
        return {'speed': self.speed}


# =============================================================================
# TMNF BINS (ActionBin dataclass objects, NOT dicts)
# =============================================================================

GAS_BINS = [
    ActionBin(bin_id=0, a_min=0.0, a_max=0.001, label="DEAD_ZONE", effect_delta=0.0),
    ActionBin(bin_id=1, a_min=0.001, a_max=1.0, label="ON", effect_delta=5.0),
]

BRAKE_BINS = [
    ActionBin(bin_id=0, a_min=0.0, a_max=0.001, label="DEAD_ZONE", effect_delta=0.0),
    ActionBin(bin_id=1, a_min=0.001, a_max=1.0, label="ON", effect_delta=-3.0),
]


def _make_tester(bins_by_action=None):
    """Create MultiplicityTester with MockAdapter and TMNF bins."""
    adapter = MockMultiplicityAdapter()
    if bins_by_action is None:
        bins_by_action = {
            'gas': GAS_BINS,
            'brake': BRAKE_BINS,
        }
    return MultiplicityTester(adapter, bins_by_action, feedback_variable='speed')


# =============================================================================
# TESTS
# =============================================================================

class TestMultiplicityTester:
    """Tests for MultiplicityTester class."""

    def test_binary_gas_no_intermediates(self):
        """
        test_action('gas') with 5 intermediates.
        All probes match either DEAD_ZONE or ON.
        new_bins_found == 0. validated == True.
        """
        tester = _make_tester()
        result = tester.test_action('gas', num_intermediates=5)

        assert isinstance(result, MultiplicityResult)
        assert result.action_name == 'gas'
        assert result.new_bins_found == 0
        assert result.validated is True
        assert len(result.probes) > 0

        # Every probe should match an existing bin
        for probe in result.probes:
            assert probe.is_new_bin is False, (
                f"Probe value {probe.probe_value} classified as new bin "
                f"(delta={probe.delta}), but should match existing bin"
            )

    def test_binary_brake_no_intermediates(self):
        """
        test_action('brake') with 5 intermediates.
        All probes match either DEAD_ZONE or ON. validated == True.
        """
        tester = _make_tester()
        result = tester.test_action('brake', num_intermediates=5)

        assert result.action_name == 'brake'
        assert result.new_bins_found == 0
        assert result.validated is True
        assert len(result.probes) > 0

        for probe in result.probes:
            assert probe.is_new_bin is False

    def test_probe_below_min_matches_dead_zone(self):
        """
        Probe value 0.0005 (below gas MIN 0.001) matches DEAD_ZONE bin (delta ~ 0.0).
        """
        tester = _make_tester()

        # Force a single probe at value 0.0005
        probe = tester._probe_value('gas', 0.0005, GAS_BINS, tolerance=0.1)

        assert probe.delta == 0.0, (
            f"Below-threshold probe should have zero delta, got {probe.delta}"
        )
        assert probe.nearest_bin.label == 'DEAD_ZONE'
        assert probe.is_new_bin is False

    def test_probe_above_min_matches_on_bin(self):
        """
        Probe value 0.5 (above gas MIN 0.001) matches ON bin (delta ~ 5.0).
        """
        tester = _make_tester()

        probe = tester._probe_value('gas', 0.5, GAS_BINS, tolerance=0.1)

        assert probe.delta == 5.0, (
            f"Above-threshold probe should have delta 5.0, got {probe.delta}"
        )
        assert probe.nearest_bin.label == 'ON'
        assert probe.is_new_bin is False

    def test_delta_matches_bin_within_tolerance(self):
        """Unit test for _delta_matches_bin with various deltas and tolerances."""
        # Exact match
        assert MultiplicityTester._delta_matches_bin(5.0, 5.0, 0.1) is True

        # Within tolerance
        assert MultiplicityTester._delta_matches_bin(5.05, 5.0, 0.1) is True
        assert MultiplicityTester._delta_matches_bin(4.95, 5.0, 0.1) is True

        # At boundary
        assert MultiplicityTester._delta_matches_bin(5.1, 5.0, 0.1) is True
        assert MultiplicityTester._delta_matches_bin(4.9, 5.0, 0.1) is True

        # Beyond tolerance
        assert MultiplicityTester._delta_matches_bin(5.2, 5.0, 0.1) is False
        assert MultiplicityTester._delta_matches_bin(4.8, 5.0, 0.1) is False

        # Zero delta (dead zone)
        assert MultiplicityTester._delta_matches_bin(0.0, 0.0, 0.1) is True
        assert MultiplicityTester._delta_matches_bin(0.05, 0.0, 0.1) is True

        # Negative delta (brake)
        assert MultiplicityTester._delta_matches_bin(-3.0, -3.0, 0.1) is True
        assert MultiplicityTester._delta_matches_bin(-2.95, -3.0, 0.1) is True
        assert MultiplicityTester._delta_matches_bin(-3.5, -3.0, 0.1) is False

    def test_test_all_runs_all_actions(self):
        """test_all() returns results for all actions in bins_by_action."""
        tester = _make_tester()
        results = tester.test_all(num_intermediates=3)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'gas', 'brake'}

        for action_name, result in results.items():
            assert isinstance(result, MultiplicityResult)
            assert result.action_name == action_name
            assert result.validated is True

    def test_rewind_called_after_each_probe(self):
        """
        Verify adapter.rewind() called after each probe.
        Speed returns to saved value after each probe cycle.
        """
        adapter = MockMultiplicityAdapter()
        bins_by_action = {'gas': GAS_BINS}
        tester = MultiplicityTester(adapter, bins_by_action, 'speed')

        initial_speed = adapter.speed

        result = tester.test_action('gas', num_intermediates=3)

        # Rewind called once per probe
        assert adapter.rewind_count == len(result.probes), (
            f"Expected {len(result.probes)} rewinds, got {adapter.rewind_count}"
        )

        # Speed should be back to initial after all probes
        assert adapter.speed == initial_speed, (
            f"Speed should be {initial_speed} after rewinds, got {adapter.speed}"
        )

    def test_save_called_for_each_probe(self):
        """save_state() called before each probe to ensure determinism."""
        adapter = MockMultiplicityAdapter()
        bins_by_action = {'gas': GAS_BINS}
        tester = MultiplicityTester(adapter, bins_by_action, 'speed')

        result = tester.test_action('gas', num_intermediates=3)

        # save_state called once per probe
        assert adapter.save_count == len(result.probes), (
            f"Expected {len(result.probes)} saves, got {adapter.save_count}"
        )

    def test_empty_bins_returns_validated(self):
        """Action with no bins returns validated=True (nothing to disprove)."""
        tester = _make_tester(bins_by_action={'gas': []})
        result = tester.test_action('gas')

        assert result.validated is True
        assert result.new_bins_found == 0
        assert len(result.probes) == 0

    def test_auto_tolerance_binary(self):
        """Auto-tolerance for binary bins (deltas: 0.0, 5.0) should be 2.5."""
        tester = _make_tester()
        tol = tester._auto_tolerance(GAS_BINS)

        # Distinct deltas: 0.0 and 5.0. Gap = 5.0. Tolerance = 5.0 / 2 = 2.5
        assert tol == 2.5, f"Expected tolerance 2.5, got {tol}"

    def test_multiplicity_probe_dataclass(self):
        """MultiplicityProbe stores all fields correctly."""
        bin_obj = GAS_BINS[1]  # ON bin
        probe = MultiplicityProbe(
            action_name='gas',
            probe_value=0.5,
            delta=5.0,
            nearest_bin=bin_obj,
            is_new_bin=False,
            tolerance=0.1
        )

        assert probe.action_name == 'gas'
        assert probe.probe_value == 0.5
        assert probe.delta == 5.0
        assert probe.nearest_bin.label == 'ON'
        assert probe.is_new_bin is False
        assert probe.tolerance == 0.1

    def test_multiplicity_result_dataclass(self):
        """MultiplicityResult stores all fields correctly."""
        result = MultiplicityResult(
            action_name='gas',
            existing_bins=GAS_BINS,
            probes=[],
            new_bins_found=0,
            validated=True
        )

        assert result.action_name == 'gas'
        assert len(result.existing_bins) == 2
        assert result.new_bins_found == 0
        assert result.validated is True
