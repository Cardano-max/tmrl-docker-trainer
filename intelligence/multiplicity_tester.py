"""
INTELLIGENCE: Multiplicity Tester - Experimental Bin Validation

Sutton Jan 31 (Pong meeting): "you must test multiples... you cannot
assume linearity"

For each discovered action, probes intermediate values between MIN and MAX
to verify whether they produce distinct state transitions or collapse into
existing bins. For TMNF's 4 binary inputs, multiplicity testing confirms
exactly 2 bins each (DEAD_ZONE and ON) with no hidden intermediates.

Generic for both binary and analog actions. No linearity assumptions --
every intermediate is probed individually using the deterministic
save_state/rewind pattern from Phase A.

LAYER: Intelligence (works with ActionBin dataclass objects).
MultiGraphManager (knowledge layer) uses ActionBin.to_dict() dicts.
The conversion boundary is at the caller level.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from intelligence.intelligence_experimentation import ActionBin

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MultiplicityProbe:
    """Result of probing one intermediate value."""
    action_name: str
    probe_value: float        # The intermediate value tested
    delta: float              # State change observed
    nearest_bin: ActionBin    # Which existing bin this delta matches
    is_new_bin: bool          # True if delta doesn't match any existing bin
    tolerance: float          # Tolerance used for matching


@dataclass
class MultiplicityResult:
    """Full result of multiplicity testing for one action."""
    action_name: str
    existing_bins: List[ActionBin]
    probes: List[MultiplicityProbe]
    new_bins_found: int       # Count of intermediates that don't match existing bins
    validated: bool           # True if no new bins found (existing bins are complete)


# =============================================================================
# MULTIPLICITY TESTER
# =============================================================================

class MultiplicityTester:
    """
    Probes intermediate action values between MIN and MAX to validate
    that bin discovery results are complete.

    Uses the same save_state/rewind probe pattern as Phase A:
      save_state -> apply action -> measure delta -> rewind

    Works with ActionBin dataclass objects (intelligence layer).
    For knowledge layer (MultiGraphManager), convert via ActionBin.to_dict().

    Constructor:
        adapter: any adapter with save_state(), rewind(), send_action_dict(),
                 wait_one_tick(), get_feedbacks()
        bins_by_action: Dict mapping action name to list of ActionBin objects
        feedback_variable: which variable to measure deltas on (default 'speed')
    """

    def __init__(
        self,
        adapter,
        bins_by_action: Dict[str, List[ActionBin]],
        feedback_variable: str = 'speed'
    ):
        self.adapter = adapter
        self.bins_by_action = bins_by_action
        self.feedback_variable = feedback_variable

    def test_action(
        self,
        action_name: str,
        num_intermediates: int = 5,
        tolerance: Optional[float] = None
    ) -> MultiplicityResult:
        """
        Probe intermediate values for one action and compare deltas
        to existing bins.

        Algorithm:
          1. Get existing bins for this action
          2. Generate probe values (between bin boundaries)
          3. For each probe: save -> apply -> measure -> rewind -> compare
          4. Report whether any probe produced a novel delta

        Args:
            action_name: Which action to test (e.g. 'gas', 'brake')
            num_intermediates: Number of intermediate points to probe
            tolerance: Delta matching tolerance. If None, auto-computed
                       from bin deltas.

        Returns:
            MultiplicityResult with all probe outcomes
        """
        bins = self.bins_by_action.get(action_name, [])
        if not bins:
            logger.warning(f"[MULTIPLICITY] No bins for action '{action_name}'")
            return MultiplicityResult(
                action_name=action_name,
                existing_bins=[],
                probes=[],
                new_bins_found=0,
                validated=True
            )

        # Auto-compute tolerance from bin deltas if not provided
        if tolerance is None:
            tolerance = self._auto_tolerance(bins)

        # Generate probe values
        probe_values = self._generate_probe_values(bins, num_intermediates)

        logger.info(
            f"[MULTIPLICITY] Testing '{action_name}': "
            f"{len(probe_values)} probes, tolerance={tolerance:.6f}"
        )

        # Probe each value
        probes = []
        for pv in probe_values:
            probe = self._probe_value(action_name, pv, bins, tolerance)
            probes.append(probe)

        new_bins_found = sum(1 for p in probes if p.is_new_bin)

        result = MultiplicityResult(
            action_name=action_name,
            existing_bins=bins,
            probes=probes,
            new_bins_found=new_bins_found,
            validated=(new_bins_found == 0)
        )

        logger.info(
            f"[MULTIPLICITY] '{action_name}': "
            f"{new_bins_found} new bins found, "
            f"validated={result.validated}"
        )

        return result

    def test_all(
        self,
        num_intermediates: int = 5
    ) -> Dict[str, MultiplicityResult]:
        """
        Run test_action for every action in bins_by_action.

        Returns:
            Dict mapping action_name to MultiplicityResult
        """
        results = {}
        for action_name in self.bins_by_action:
            results[action_name] = self.test_action(
                action_name, num_intermediates
            )
        return results

    def _probe_value(
        self,
        action_name: str,
        probe_value: float,
        bins: List[ActionBin],
        tolerance: float
    ) -> MultiplicityProbe:
        """
        Probe a single intermediate value using save/rewind pattern.

        Steps:
          1. save_state()
          2. Read feedback_before
          3. Send action with probe_value
          4. wait_one_tick()
          5. Read feedback_after
          6. delta = after - before
          7. rewind()
          8. Compare delta to existing bins
        """
        # Save state for deterministic rewind
        self.adapter.save_state()

        # Read feedback before action
        fb_before = self.adapter.get_feedbacks()
        value_before = fb_before[self.feedback_variable]

        # Send action with only this action set to probe_value
        action_dict = {action_name: probe_value}
        self.adapter.send_action_dict(action_dict)

        # Advance one tick
        self.adapter.wait_one_tick()

        # Read feedback after action
        fb_after = self.adapter.get_feedbacks()
        value_after = fb_after[self.feedback_variable]

        # Compute delta
        delta = value_after - value_before

        # Rewind to saved state
        self.adapter.rewind()

        # Compare delta to existing bins
        nearest_bin, is_new = self._find_nearest_bin(delta, bins, tolerance)

        return MultiplicityProbe(
            action_name=action_name,
            probe_value=probe_value,
            delta=delta,
            nearest_bin=nearest_bin,
            is_new_bin=is_new,
            tolerance=tolerance
        )

    def _generate_probe_values(
        self,
        bins: List[ActionBin],
        num_intermediates: int
    ) -> List[float]:
        """
        Generate probe values to test between bin boundaries.

        For binary inputs (2 bins: DEAD_ZONE + ON):
          - Below MIN: min/2, min/4 (should be dead zone)
          - Above MIN: min*2, min*10, 0.5 (should be ON)
          - Between 0 and MIN: linspace(0, min, num_intermediates)

        For analog inputs (many bins):
          - Midpoints between adjacent bins
          - 1/3 and 2/3 points if num_intermediates > 1
        """
        if len(bins) <= 2:
            return self._generate_binary_probes(bins, num_intermediates)
        else:
            return self._generate_analog_probes(bins, num_intermediates)

    def _generate_binary_probes(
        self,
        bins: List[ActionBin],
        num_intermediates: int
    ) -> List[float]:
        """
        Generate probes for binary inputs.

        Binary input has 2 bins:
          bin 0 (DEAD_ZONE): a_min=0.0, a_max=some_threshold
          bin 1 (ON): a_min=threshold, a_max=1.0

        Probe below, around, and above the threshold.
        """
        probes = []

        # Find the threshold (ON bin's a_min)
        on_bin = None
        for b in bins:
            if b.bin_id != 0:
                on_bin = b
                break

        if on_bin is None:
            # Only dead zone, nothing to test
            return [0.0]

        threshold = on_bin.a_min

        # Below threshold (should match dead zone)
        if threshold > 0:
            probes.append(threshold / 2.0)
            probes.append(threshold / 4.0)
            # Linspace between 0 and threshold
            if num_intermediates > 0:
                step = threshold / (num_intermediates + 1)
                for i in range(1, num_intermediates + 1):
                    val = step * i
                    if val not in probes:
                        probes.append(val)

        # Above threshold (should match ON bin)
        probes.append(threshold * 2.0)
        probes.append(threshold * 10.0)
        probes.append(0.5)

        # Deduplicate and sort
        probes = sorted(set(probes))

        return probes

    def _generate_analog_probes(
        self,
        bins: List[ActionBin],
        num_intermediates: int
    ) -> List[float]:
        """
        Generate probes for analog inputs with many bins.

        For each pair of adjacent bins, probe midpoint and optionally
        1/3 and 2/3 points.
        """
        probes = []

        # Sort bins by a_min
        sorted_bins = sorted(bins, key=lambda b: b.a_min)

        for i in range(len(sorted_bins) - 1):
            lo = sorted_bins[i].a_max
            hi = sorted_bins[i + 1].a_min

            if hi > lo:
                # Gap between bins -- probe inside
                mid = (lo + hi) / 2.0
                probes.append(mid)

                if num_intermediates > 1:
                    probes.append(lo + (hi - lo) / 3.0)
                    probes.append(lo + 2 * (hi - lo) / 3.0)

            # Also probe midpoint of each bin's range
            bin_mid = (sorted_bins[i].a_min + sorted_bins[i].a_max) / 2.0
            if bin_mid not in probes:
                probes.append(bin_mid)

        # Midpoint of last bin
        last = sorted_bins[-1]
        last_mid = (last.a_min + last.a_max) / 2.0
        if last_mid not in probes:
            probes.append(last_mid)

        return sorted(set(probes))

    def _find_nearest_bin(
        self,
        delta: float,
        bins: List[ActionBin],
        tolerance: float
    ) -> tuple:
        """
        Find which existing bin's effect_delta matches the observed delta.

        Returns:
            (nearest_bin, is_new_bin): The closest matching bin and whether
            the delta is beyond tolerance of all bins.
        """
        best_bin = bins[0]
        best_diff = abs(delta - bins[0].effect_delta)

        for b in bins:
            diff = abs(delta - b.effect_delta)
            if diff < best_diff:
                best_diff = diff
                best_bin = b

        is_new = not self._delta_matches_bin(delta, best_bin.effect_delta, tolerance)

        return best_bin, is_new

    @staticmethod
    def _delta_matches_bin(
        delta: float,
        bin_delta: float,
        tolerance: float
    ) -> bool:
        """
        Check if an observed delta matches a bin's known effect_delta.

        For binary inputs with large bin deltas (e.g. 0.6 for gas),
        tolerance of 0.1 is appropriate. For analog with fine precision,
        use smaller tolerance.

        Returns:
            True if abs(delta - bin_delta) <= tolerance
        """
        return abs(delta - bin_delta) <= tolerance

    def _auto_tolerance(self, bins: List[ActionBin]) -> float:
        """
        Compute appropriate tolerance from bin deltas.

        Strategy: half the minimum non-zero gap between distinct bin deltas.
        Falls back to 0.1 if all bins have same delta or only one bin.
        """
        deltas = sorted(set(abs(b.effect_delta) for b in bins))

        if len(deltas) <= 1:
            return 0.1

        # Minimum gap between distinct delta values
        min_gap = float('inf')
        for i in range(len(deltas) - 1):
            gap = deltas[i + 1] - deltas[i]
            if gap > 0:
                min_gap = min(min_gap, gap)

        if min_gap == float('inf'):
            return 0.1

        return min_gap / 2.0
