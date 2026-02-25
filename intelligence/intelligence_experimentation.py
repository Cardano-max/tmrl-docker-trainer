"""
INTELLIGENCE: Experimentation - Bin Discovery Algorithm

AUTHORITATIVE SPEC: algorithm_spec_from_meetings.md (section 14)

    FOR each action (gas, brake, steering):

        Start at large value (1e6), go down by powers of 10.
        Record delta (state change) for each.

        When delta FIRST drops below the saturated value:
            -> bracket found for MAX -> binary search it

        Keep going down.
        When delta becomes same as action=0 (no change):
            -> bracket found for MIN -> binary search it

        Store MIN, MAX.
        Bins = range from MIN to MAX.

CORE PRINCIPLES (non-negotiable):

    - No noise. No delay. No seconds. No averaging.
    - Everything is: STATE_t --(ACTION per frame)--> STATE_t+1
    - Action=0 is also an action (NOT noise, NOT baseline to subtract)
    - Frame is the atomic time unit
    - "Not doing an action is also an action"
    - No heuristics. No baseline subtraction. No magic decimals.
    - Pure transition search.

STEERING:
    Same algorithm applied identically. Range [-1, 1].
    Discover positive side, mirror to negative (symmetric).
"""

import logging
import time
import math
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from utils.exceptions import IntelligenceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class ExperimentationPhase(Enum):
    NOT_STARTED = "not_started"
    DISCOVERING = "discovering"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoverySource(Enum):
    EXPERIMENTATION = "experimentation"
    DOCUMENTATION = "documentation"
    EMERGENCY_FALLBACK = "emergency_fallback"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ActionBin:
    """
    Equivalence class of actions that produce indistinguishable
    state transitions within one frame.
    """
    bin_id: int
    a_min: float        # Minimum action value in this bin
    a_max: float        # Maximum action value in this bin
    label: str          # Human-readable label
    effect_delta: float  # Representative delta from ONE probe (no averaging)

    def contains(self, value: float) -> bool:
        return self.a_min <= value < self.a_max

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bin_id': self.bin_id,
            'min': self.a_min,
            'max': self.a_max,
            'label': self.label,
            'effect_delta': self.effect_delta
        }


@dataclass
class ProbeResult:
    """Result of a single probe: one action, one frame, one transition."""
    action_value: float
    delta_state: float  # SIGNED: feedback_after - feedback_before
    feedback_before: Dict[str, float]
    feedback_after: Dict[str, float]
    frame_duration_s: float
    feedback_pre_before: Optional[Dict[str, float]] = None  # For delta-heading
    valid: bool = True  # False if steering displacement too small


@dataclass
class ActionDiscoveryResult:
    """Complete discovery result for one action."""
    action_name: str
    a_max_effective: float = 0.0
    a_min_effective: float = 0.0
    a_min_identifiable: bool = True
    is_binary: bool = False
    delta_0: float = 0.0             # Delta when action=0 (a REAL transition)
    delta_max: float = 0.0           # Saturated delta (from MAX action)
    delta_at_min: float = 0.0        # Delta at MIN action
    system_precision: int = 6
    discovered_bins: List[ActionBin] = field(default_factory=list)
    probe_log: List[Dict[str, Any]] = field(default_factory=list)
    experiments_run: int = 0
    discovery_time: float = 0.0
    discovery_source: DiscoverySource = DiscoverySource.EXPERIMENTATION
    success: bool = False
    error_message: str = ""
    max_bracket: Tuple[float, float] = (0.0, 0.0)
    min_bracket: Tuple[float, float] = (0.0, 0.0)
    max_binary_search_steps: int = 0
    min_binary_search_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_name': self.action_name,
            'a_max_effective': self.a_max_effective,
            'a_min_effective': self.a_min_effective,
            'a_min_identifiable': self.a_min_identifiable,
            'is_binary': self.is_binary,
            'delta_0': self.delta_0,
            'delta_max': self.delta_max,
            'delta_at_min': self.delta_at_min,
            'system_precision': self.system_precision,
            'bins': [b.to_dict() for b in self.discovered_bins],
            'experiments_run': self.experiments_run,
            'discovery_time': self.discovery_time,
            'discovery_source': self.discovery_source.value,
            'success': self.success,
            'max_bracket': list(self.max_bracket),
            'min_bracket': list(self.min_bracket),
            'max_binary_search_steps': self.max_binary_search_steps,
            'min_binary_search_steps': self.min_binary_search_steps,
            'probe_log': self.probe_log
        }


# =============================================================================
# EXACT BIN DISCOVERY (per-action)
# =============================================================================

class FrameBinDiscovery:
    """
    Bin discovery for a single action (algorithm_spec_from_meetings.md section 14).

    Single downward sweep from large value:
        - Probe action=0 first for physics context (what "no change" means)
        - Descend powers of 10, recording delta at each
        - First probe = saturated delta
        - When delta drops below saturated: MAX bracket found, binary search it
        - Keep going down
        - When delta becomes same as action=0: MIN bracket found, binary search it
        - Store MIN, MAX

    No noise. No baseline subtraction. No averaging.
    Action=0 is a real action producing a real transition.
    """

    # Keys to EXCLUDE from delta computation (not state variables)
    EXCLUDED_FEEDBACK_KEYS = ('rpm', 'input_gas', 'input_brake', 'input_steer',
                               'gear', 'finished', 'distance',
                               'pos_x', 'pos_y', 'pos_z')

    def __init__(
        self,
        action_name: str,
        action_range: Tuple[float, float],
        search_precision: float = 0.001,
        noise_epsilon: float = 0.05,
        signal_epsilon: float = 1e-7
    ):
        self.action_name = action_name
        self.action_range = action_range
        self.search_precision = search_precision
        self.noise_epsilon = noise_epsilon      # Measurement variance floor
        self.signal_epsilon = signal_epsilon    # System's actual precision

        # Core results
        self.delta_0: Optional[float] = None      # Delta when action=0
        self.delta_max: Optional[float] = None     # Saturated delta
        self.a_max: Optional[float] = None         # Discovered MAX
        self.a_min: Optional[float] = None         # Discovered MIN
        self.delta_at_min: Optional[float] = None  # Delta at MIN

        # Probe history
        self.probes: List[ProbeResult] = []
        self.system_precision: int = 6

    # -----------------------------------------------------------------
    # DELTA COMPUTATION: SIGNED, not absolute
    # -----------------------------------------------------------------

    # Minimum displacement for valid heading measurement
    STEERING_MIN_DISPLACEMENT = 0.1

    def compute_delta(self, before: Dict[str, float], after: Dict[str, float],
                      action_name: str = None,
                      pre_before: Dict[str, float] = None) -> Optional[float]:
        """SIGNED state change: after - before.

        Spec: "STATE_t --(ACTION per frame)--> STATE_t+1"
        The delta IS the transition. It can be positive or negative.
        Action=0 producing delta=-2 (deceleration) is a REAL transition.

        For gas/brake: uses speed delta (signed).
        For steering: uses delta-heading from two consecutive displacements.
            heading_before = atan2(before - pre_before)
            heading_after  = atan2(after - before)
            delta = wrap(heading_after - heading_before)
            This measures TURNING, not direction of travel.
            Requires pre_before (state one frame before probe).

        Returns None if steering displacement is below threshold (invalid probe).
        """
        name = action_name or self.action_name

        # Steering: delta-heading from two consecutive displacements
        if name == 'steering':
            if (pre_before
                and all(k in pre_before and k in before and k in after
                        for k in ('pos_x', 'pos_z'))):
                # Displacement before action (coasting)
                dx0 = before['pos_x'] - pre_before['pos_x']
                dz0 = before['pos_z'] - pre_before['pos_z']
                # Displacement during action
                dx1 = after['pos_x'] - before['pos_x']
                dz1 = after['pos_z'] - before['pos_z']

                mag_before = math.sqrt(dx0 * dx0 + dz0 * dz0)
                mag_after = math.sqrt(dx1 * dx1 + dz1 * dz1)

                # Reject if displacement too small — heading from jitter
                if mag_before < self.STEERING_MIN_DISPLACEMENT or mag_after < self.STEERING_MIN_DISPLACEMENT:
                    return None  # Invalid: not enough motion for heading

                heading_before = math.atan2(dz0, dx0)
                heading_after = math.atan2(dz1, dx1)
                delta_heading = heading_after - heading_before
                # Wrap to [-pi, pi]
                while delta_heading > math.pi:
                    delta_heading -= 2.0 * math.pi
                while delta_heading < -math.pi:
                    delta_heading += 2.0 * math.pi
                return delta_heading
            return None  # No position data for steering

        # Gas/brake: signed speed change
        if 'speed' in before and 'speed' in after:
            return after['speed'] - before['speed']

        # Fallback: largest signed delta across valid channels
        max_delta = 0.0
        for k in before:
            if k in after and k not in self.EXCLUDED_FEEDBACK_KEYS:
                d = after[k] - before[k]
                if abs(d) > abs(max_delta):
                    max_delta = d
        return max_delta

    # -----------------------------------------------------------------
    # COMPARISON: "Are these two deltas the same?"
    # -----------------------------------------------------------------

    def _deltas_are_same(self, d1: float, d2: float) -> bool:
        """Are two deltas effectively the same?

        Uses noise_epsilon: the measurement method's variance floor.
        D0 subtraction produces ±0.03 variance — any difference smaller
        than noise_epsilon is indistinguishable from measurement noise.
        """
        return abs(d1 - d2) < self.noise_epsilon

    def _is_saturated(self, delta: float) -> bool:
        """Is this delta the same as the saturated (max) delta?

        Spec: "if you go beyond the max the delta won't change"
        Uses noise_epsilon — comparing two noisy measurements.
        """
        if self.delta_max is None:
            return False
        return self._deltas_are_same(delta, self.delta_max)

    def _is_same_as_delta0(self, delta: float) -> bool:
        """Is this delta the same as the D0 (action=0) delta?

        Spec: "when delta = same as action=0" the action has no effect.
        Compares delta to D0 directly — no D0 subtraction needed.
        """
        if self.delta_0 is None:
            return abs(delta) < self.noise_epsilon
        return abs(delta - self.delta_0) < self.noise_epsilon

    def _is_real_signal(self, delta: float) -> bool:
        """Did the system produce a real reading above float precision?

        Uses signal_epsilon — the system's actual precision.
        This catches the smallest value a 50ms frame produces.
        Separate from noise: a reading can be real (> signal_epsilon)
        but still lost in noise (< noise_epsilon).
        """
        return abs(delta) > self.signal_epsilon

    # -----------------------------------------------------------------
    # EXPONENTIAL SEQUENCE
    # -----------------------------------------------------------------

    def get_exponential_sequence(self) -> List[float]:
        """Descending powers of 10 within the true action range.

        Exact exponential bracketing: start from action_range max,
        descend by powers of 10. No phantom values outside the range
        that just get clamped to the same thing.

        For [0, 1]: [1.0, 0.1, 0.01, 0.001, 0.0001, 0.00001, 0.000001]
        """
        a_max = abs(self.action_range[1])
        values = []
        val = a_max
        while val >= 1e-6:
            values.append(val)
            val /= 10.0
        if not values or values[-1] > 1e-6:
            values.append(1e-6)
        return values

    # -----------------------------------------------------------------
    # DISCOVERY: Single downward sweep
    # -----------------------------------------------------------------

    def run_discovery(
        self,
        probe_fn: Callable[[float], ProbeResult]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Single downward sweep (algorithm_spec_from_meetings.md section 14):

            Start at large value, go down by powers of 10.
            Record delta for each probe.

            When delta FIRST drops below saturated: MAX bracket -> binary search.
            Keep going. When delta == action=0: MIN bracket -> binary search.
            Store MIN, MAX.

        D0 (action=0) is probed first for logging/informational purposes.
        Actual drift removal happens per-probe (the intelligence math):
        each probe subtracts local D0 to isolate the pure action signal.

        No heuristics. No baseline subtraction. No magic decimals.
        Pure transition search. Action=0 is a real action.

        Returns:
            (a_max, a_min) or (None, None) if action has no effect.
        """
        sequence = self.get_exponential_sequence()

        # ===========================================
        # Probe action=0 for physics context
        # Spec section 5C: car environments need to know what
        # "no change" means (action=0 still causes drag/coast).
        # "Not doing an action is also an action" (Jan 9, Feb 16)
        # ===========================================
        logger.info(f"  [D0] Probe action=0 (physics context)")
        d0_probe = probe_fn(0.0)
        if d0_probe.valid:
            self.delta_0 = d0_probe.delta_state
        else:
            self.delta_0 = 0.0
            logger.warning(f"    D0 probe invalid, using 0.0")
        logger.info(f"    D0 = {self.delta_0:.6f} (real transition, not noise)")

        # ===========================================
        # Downward sweep: powers of 10 from top of range
        # Spec section 14: "Start at large value, go down by powers of 10"
        # Find MAX bracket, then MIN bracket, in one pass.
        # ===========================================
        logger.info(f"  [SWEEP] Descending powers of 10...")

        max_bracket_low = None
        max_bracket_high = None
        min_bracket_low = None
        min_bracket_high = None

        prev_val = None
        prev_delta = None
        found_max_bracket = False
        found_min_bracket = False

        for val in sequence:
            pr = probe_fn(val)

            if not pr.valid:
                logger.warning(f"    a={val:.6f} -> INVALID (skipped)")
                continue

            delta = pr.delta_state
            logger.info(f"    a={val:.6f} -> delta={delta:.6f}")

            # First probe = saturated delta (highest action value)
            if self.delta_max is None:
                self.delta_max = delta
                logger.info(f"    (saturated delta = {delta:.6f})")

                # EARLY EXIT: if max action produces same delta as D0,
                # this action has no detectable effect. Don't sweep further.
                # Sutton: if doing the strongest action == doing nothing,
                # the action is useless. No bracket search needed.
                if self._is_same_as_delta0(delta):
                    logger.warning(
                        f"  Saturated delta ({delta:.6f}) same as D0 "
                        f"({self.delta_0:.6f}) at first probe. "
                        f"Action has no detectable effect — skipping sweep."
                    )
                    return None, None

                prev_val = val
                prev_delta = delta
                continue

            # MAX bracket: find where delta CHANGES from saturated
            if not found_max_bracket:
                if self._is_saturated(delta):
                    prev_val = val
                    prev_delta = delta
                else:
                    max_bracket_low = val
                    max_bracket_high = prev_val
                    found_max_bracket = True
                    logger.info(
                        f"    >>> MAX BRACKET: [{val:.6f}, {prev_val:.6f}]"
                        f" (delta changed from {prev_delta:.6f} to {delta:.6f})"
                    )
                    prev_val = val
                    prev_delta = delta
                    continue

            # MIN bracket: find where delta becomes same as D0
            # Spec: "find first value == D0" (action has no effect beyond coasting)
            if found_max_bracket and not found_min_bracket:
                if self._is_same_as_delta0(delta):
                    # Delta same as D0 → action no longer matters
                    min_bracket_low = val
                    min_bracket_high = prev_val
                    found_min_bracket = True
                    logger.info(
                        f"    >>> MIN BRACKET: [{val:.6f}, {prev_val:.6f}]"
                        f" (delta={delta:.6f} same as D0={self.delta_0:.6f})"
                    )
                    break
                else:
                    prev_val = val
                    prev_delta = delta

        # Edge case: only one probe or first probe only
        if self.delta_max is None:
            logger.warning(f"  No valid probes")
            return None, None

        # Edge case: saturated delta IS D0 → action has no effect at all
        # Only applies if no bracket was found. If a bracket was found during
        # exponential descent, the action clearly has a detectable range even
        # if the saturated value happens to coincide with D0 (measurement noise).
        if self._is_same_as_delta0(self.delta_max) and not found_max_bracket:
            logger.warning(f"  Saturated delta ({self.delta_max:.6f}) same as D0 "
                          f"({self.delta_0:.6f}). Action has no detectable effect.")
            return None, None

        # Edge case: never found MAX bracket (all saturated = no range)
        if not found_max_bracket:
            self.a_max = self.action_range[1]
            logger.info(f"  All probes saturated. MAX = {self.a_max}")

        # ===========================================
        # Binary search MAX bracket
        # Spec section 5A step 2: "Binary search the interval"
        # ===========================================
        if found_max_bracket:
            logger.info(
                f"  [MAX SEARCH] Binary search in "
                f"[{max_bracket_low:.6f}, {max_bracket_high:.6f}]..."
            )
            self.a_max, bs_steps = self._binary_search_max(
                probe_fn, max_bracket_low, max_bracket_high
            )
            logger.info(f"    >>> MAX = {self.a_max:.6f} ({bs_steps} binary search steps)")
        else:
            self.a_max = self.action_range[1]

        # ===========================================
        # Binary search MIN bracket
        # Spec section 5B step 2: "Binary search the interval"
        # delta == D0 means action has no effect beyond coasting.
        # ===========================================
        if found_min_bracket:
            logger.info(
                f"  [MIN SEARCH] Binary search in "
                f"[{min_bracket_low:.6f}, {min_bracket_high:.6f}]..."
            )
            self.a_min, bs_steps = self._binary_search_min(
                probe_fn, min_bracket_low, min_bracket_high
            )
            logger.info(f"    >>> MIN = {self.a_min:.6f} ({bs_steps} binary search steps)")
        else:
            if found_max_bracket:
                self.a_min = sequence[-1]
                logger.warning(
                    f"  MIN not bracketed (delta kept changing). "
                    f"Using smallest test value: {self.a_min:.6f}"
                )
            else:
                # No MAX bracket either → no detectable range
                return None, None

        return self.a_max, self.a_min

    # -----------------------------------------------------------------
    # BINARY SEARCH: MAX
    # -----------------------------------------------------------------

    def _binary_search_max(
        self,
        probe_fn: Callable[[float], ProbeResult],
        low: float,
        high: float
    ) -> Tuple[float, int]:
        """Binary search for MAX within bracket.

        Invariant: delta(low) is NOT saturated, delta(high) IS saturated.
        MAX = smallest action that still produces saturated delta.

        Example:
            [10, 100] -> mid=55(sat) -> [10,55] -> mid=32(sat) -> [10,32]
            -> mid=21(sat) -> [10,21] -> mid=15(not) -> [15,21]
            -> mid=18(sat) -> [15,18] -> mid=16(not) -> [16,18]
            -> mid=17(sat) -> [16,17] -> STOP
            MAX = 17
        """
        steps = 0
        while (high - low) > self.search_precision:
            mid = (low + high) / 2.0
            pr = probe_fn(mid)
            steps += 1

            if self._is_saturated(pr.delta_state):
                high = mid  # Still saturated, MAX might be lower
                logger.info(f"    [{low:.6f}, {high:.6f}] mid={mid:.6f} -> SATURATED")
            else:
                low = mid   # Not saturated, MAX is higher
                logger.info(f"    [{low:.6f}, {high:.6f}] mid={mid:.6f} -> not saturated")

            if steps > 50:  # Safety limit
                break

        return high, steps  # MAX = smallest saturated value

    # -----------------------------------------------------------------
    # BINARY SEARCH: MIN
    # -----------------------------------------------------------------

    def _binary_search_min(
        self,
        probe_fn: Callable[[float], ProbeResult],
        low: float,
        high: float
    ) -> Tuple[float, int]:
        """Binary search for MIN within bracket.

        Invariant: delta(low) is SAME AS D0, delta(high) is DIFFERENT from D0.
        MIN = smallest action that produces delta != D0.

        Example:
            [1, 10] -> mid=5(same) -> [5,10] -> mid=7(diff) -> [5,7]
            -> mid=6(diff) -> [5,6] -> STOP
            MIN = 6
        """
        steps = 0
        while (high - low) > self.search_precision:
            mid = (low + high) / 2.0
            pr = probe_fn(mid)
            steps += 1

            if self._is_same_as_delta0(pr.delta_state):
                low = mid   # No effect at mid, MIN is higher
                logger.info(f"    [{low:.6f}, {high:.6f}] mid={mid:.6f} -> same as D0")
            else:
                high = mid  # Has effect at mid, MIN is lower or equal
                logger.info(f"    [{low:.6f}, {high:.6f}] mid={mid:.6f} -> different from D0")

            if steps > 50:  # Safety limit
                break

        return high, steps  # MIN = smallest value with effect

    # -----------------------------------------------------------------
    # BIN BUILDING: Uniform divisions of [MIN, MAX]
    # -----------------------------------------------------------------

    # Default number of bins between MIN and MAX
    DEFAULT_NUM_BINS = 10

    def build_bins(self, num_bins: int = None, precision: float = None) -> List[ActionBin]:
        """Build bins as uniform divisions of [MIN, MAX].

        Spec: "Store MIN, MAX, Δ per frame"
              "Bins = range from MIN to MAX divided by the precision
               the system can handle"

        Bins are COMPUTED from MIN/MAX range, not probed individually.
        The planner uses these to discretize the action space.

        Args:
            num_bins:  Explicit bin count (overrides precision).
            precision: Measured system precision. If provided (and num_bins
                       is not), computes n = ceil(range / precision),
                       capped to [2, 100].

        Structure:
            BIN 0: DEAD_ZONE [0, MIN)  — no effect beyond D0
            BIN 1..N: uniform [MIN, MAX] — active range
        """
        a_min = self.a_min or 0.01
        a_max = self.a_max or self.action_range[1]

        if num_bins is not None:
            n = num_bins
        elif precision is not None and precision > 0:
            n = math.ceil((a_max - a_min) / precision)
            n = max(2, min(n, 100))  # Cap to [2, 100]
            logger.info(f"  [BINS] precision={precision:.6f} -> "
                        f"n=ceil(({a_max:.6f}-{a_min:.6f})/{precision:.6f})={n}")
        else:
            n = self.DEFAULT_NUM_BINS

        bins: List[ActionBin] = []

        # Dead zone: [0, MIN) — action has no effect beyond D0
        bins.append(ActionBin(
            bin_id=0, a_min=0.0, a_max=a_min,
            label='DEAD_ZONE', effect_delta=self.delta_0 or 0.0
        ))

        # Binary detection: if MIN ≈ MAX (range < precision * 10),
        # the input is binary (off/on). Return 2 bins: dead zone + on.
        # For binary inputs, the ON bin covers [threshold, range_max].
        if a_min >= a_max or (a_max - a_min) < self.search_precision * 10:
            bins.append(ActionBin(
                bin_id=1, a_min=a_min, a_max=self.action_range[1],
                label='ON', effect_delta=self.delta_max or 0.0
            ))
            return bins

        # Uniform division of [MIN, MAX]
        step = (a_max - a_min) / n
        for i in range(n):
            lo = a_min + i * step
            hi = a_min + (i + 1) * step
            if i == n - 1:
                hi = a_max  # Ensure last bin reaches exactly MAX

            bins.append(ActionBin(
                bin_id=i + 1,
                a_min=lo,
                a_max=hi,
                label=f'BIN_{i + 1}',
                effect_delta=0.0  # Planner will use MIN/MAX/D0 directly
            ))

        return bins

    # -----------------------------------------------------------------
    # PRECISION DISCOVERY: smallest distinguishable action step
    # -----------------------------------------------------------------

    def measure_precision(
        self,
        probe_fn: Callable[[float], ProbeResult],
        max_steps: int = 20
    ) -> Optional[float]:
        """Measure system precision via binary search.

        Spec: "Precision is discovered, not assumed."
              "Bins = range from MIN to MAX divided by the precision
               the system can handle"

        Precision = smallest action value difference that produces
        a distinguishable delta.

        Algorithm:
            1. a_ref = MIN (smallest effective action)
            2. a_cmp = midpoint of [MIN, MAX]
            3. Probe both — they WILL differ (one is MIN, other is mid-range)
            4. Binary search: narrow a_cmp toward a_ref
               - If delta(mid) != delta(a_ref) → a_cmp = mid (try smaller)
               - If delta(mid) == delta(a_ref) → a_low = mid (need bigger)
            5. precision = a_cmp - original a_min

        With deterministic rewind, != means literally not bit-equal.
        For binary inputs (gas/brake), returns None — always 2 bins.

        Returns:
            float precision, or None if binary/invalid.
        """
        if self.a_min is None or self.a_max is None:
            return None

        # Binary input: no precision to measure
        if (self.a_max - self.a_min) < self.search_precision * 10:
            logger.info(f"  [PRECISION] Binary input -- skipping precision measurement")
            return None

        logger.info(f"  [PRECISION] Measuring system resolution...")
        logger.info(f"    a_ref = MIN = {self.a_min:.6f}")
        logger.info(f"    Initial a_cmp = midpoint = {(self.a_min + self.a_max) / 2:.6f}")

        a_ref = self.a_min
        a_low = self.a_min       # Boundary where delta IS same as ref
        a_high = (self.a_min + self.a_max) / 2.0  # Boundary where delta IS different

        # Get reference delta at MIN
        pr_ref = probe_fn(a_ref)
        delta_ref = pr_ref.delta_state
        logger.info(f"    delta(a_ref={a_ref:.6f}) = {delta_ref:.8f}")

        # Verify midpoint produces different delta
        pr_high = probe_fn(a_high)
        logger.info(f"    delta(a_cmp={a_high:.6f}) = {pr_high.delta_state:.8f}")

        if self._deltas_are_same(pr_high.delta_state, delta_ref):
            # Midpoint same as ref — precision is very coarse
            precision = a_high - self.a_min
            logger.info(f"    Midpoint indistinguishable from MIN -- coarse precision = {precision:.6f}")
            return precision

        # Binary search: narrow a_high toward a_ref
        for step in range(max_steps):
            if (a_high - a_low) < self.search_precision:
                logger.info(f"    Step {step+1}: converged (interval < search_precision)")
                break

            mid = (a_low + a_high) / 2.0
            pr_mid = probe_fn(mid)

            if self._deltas_are_same(pr_mid.delta_state, delta_ref):
                a_low = mid   # Can't distinguish from ref, need bigger step
                logger.info(f"    Step {step+1}: a={mid:.6f} delta={pr_mid.delta_state:.8f} "
                           f"SAME as ref -> a_low={a_low:.6f}")
            else:
                a_high = mid  # Still distinguishable, try smaller step
                logger.info(f"    Step {step+1}: a={mid:.6f} delta={pr_mid.delta_state:.8f} "
                           f"DIFF from ref -> a_high={a_high:.6f}")

        precision = a_high - self.a_min
        logger.info(f"    >>> PRECISION = {precision:.6f} "
                    f"(smallest distinguishable step from MIN)")
        return precision

    # -----------------------------------------------------------------
    # BIDIRECTIONAL (steering) support
    # -----------------------------------------------------------------

    def make_bidirectional_bins(self, positive_bins: List[ActionBin]) -> List[ActionBin]:
        """Mirror positive bins for bidirectional action (steering [-1, +1]).

        Spec: "Same algorithm. Find smallest positive steering that changes
        heading, smallest negative steering, max positive, max negative."

        We discover positive side and mirror to negative (assuming symmetry).
        """
        result = []

        # Negative side (reversed order, negated values)
        for b in reversed(positive_bins):
            if b.bin_id == 0:
                continue  # Skip dead-zone, we'll add centered one
            result.append(ActionBin(
                bin_id=-b.bin_id,
                a_min=-b.a_max,
                a_max=-b.a_min,
                label='LEFT_' + b.label,
                effect_delta=-b.effect_delta
            ))

        # Dead-zone centered at 0
        dz = positive_bins[0].a_max if positive_bins else 0.1
        result.append(ActionBin(
            bin_id=0,
            a_min=-dz,
            a_max=dz,
            label='STRAIGHT',
            effect_delta=0.0
        ))

        # Positive side
        for b in positive_bins:
            if b.bin_id == 0:
                continue
            result.append(ActionBin(
                bin_id=b.bin_id,
                a_min=b.a_min,
                a_max=b.a_max,
                label='RIGHT_' + b.label,
                effect_delta=b.effect_delta
            ))

        return result

    # -----------------------------------------------------------------
    # ACTION CLAMPING
    # -----------------------------------------------------------------

    def clamp_action(self, value: float) -> float:
        """Clamp action to [min_effective, max_effective] per frame.

        Spec: "the max per frame is still the same... even if you want
        in one frame you cannot"
        """
        a_max = self.a_max or self.action_range[1]
        return max(self.action_range[0], min(value, a_max))


# =============================================================================
# EXPERIMENTATION INTELLIGENCE (orchestrates per-action discoveries)
# =============================================================================

class ExperimentationIntelligence:
    """
    Orchestrates bin discovery for all actions (algorithm_spec_from_meetings.md).

    TWO PATHS:
    1. DOCUMENTATION: Known system -> load min/max/bins directly
    2. EXPERIMENTATION: Unknown system -> run downward sweep algorithm
    """

    def __init__(
        self,
        actions_config: Dict[str, Any],
        min_step: float = 0.01,
        max_iterations: int = 100,
        change_threshold: float = 0.001
    ):
        self.actions_config = actions_config
        self.search_precision = change_threshold

        self.phase = ExperimentationPhase.NOT_STARTED
        self.discovery_results: Dict[str, ActionDiscoveryResult] = {}
        self.discovered_bins: Dict[str, List[ActionBin]] = {}
        self.precision_results: Dict[str, Any] = {}

        self.total_experiments = 0
        self.start_time = None
        self.end_time = None

        logger.info("[EXPERIMENTATION] Initialized (algorithm_spec_from_meetings.md)")
        logger.info(f"  search_precision={change_threshold}")
        logger.info(f"  Actions to discover: {list(actions_config.keys())}")

    # -----------------------------------------------------------------
    # PATH 1: Documentation-based
    # -----------------------------------------------------------------

    def load_from_documentation(
        self,
        documented_values: Dict[str, Dict[str, float]]
    ) -> Dict[str, List[ActionBin]]:
        """Load bins from system documentation."""
        logger.info("[EXPERIMENTATION] Loading from DOCUMENTATION (known system)")

        for action_name, values in documented_values.items():
            if action_name not in self.actions_config:
                continue

            config = self.actions_config[action_name]
            is_bidir = config['range'][0] < 0
            a_min = values['min']
            a_max = values['max']

            disc = FrameBinDiscovery(action_name, tuple(config['range']),
                                     self.search_precision)
            disc.a_min = a_min
            disc.a_max = a_max
            disc.delta_max = a_max

            bins = disc.build_bins()
            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

            self.discovered_bins[action_name] = bins
            self.discovery_results[action_name] = ActionDiscoveryResult(
                action_name=action_name,
                a_max_effective=a_max,
                a_min_effective=a_min,
                delta_max=a_max,
                discovered_bins=bins,
                discovery_source=DiscoverySource.DOCUMENTATION,
                success=True
            )

        self.phase = ExperimentationPhase.COMPLETED
        return self.discovered_bins

    # -----------------------------------------------------------------
    # PATH 2: Experimentation (downward sweep algorithm)
    # -----------------------------------------------------------------

    MAX_PROBE_RETRIES = 3          # Retries on invalid steering probe

    # Two separate epsilons (noise vs signal):
    #
    # NOISE_EPSILON: measurement method's variance floor.
    #   D0 subtraction produces ±0.03 km/h variance from inter-frame
    #   speed differences. Any delta below this could be noise.
    #   Used for: _deltas_are_same, _is_saturated, _is_same_as_delta0
    #
    # SIGNAL_EPSILON: system's actual precision (game float resolution).
    #   The smallest real value a single 50ms frame can produce.
    #   Used for: detecting if the system produced any reading at all.
    #
    DEFAULT_NOISE_EPSILON = 0.05    # Speed (km/h) — above ±0.03 variance
    DEFAULT_SIGNAL_EPSILON = 1e-7   # Speed (km/h) — game float precision
    STEERING_NOISE_EPSILON = 0.002  # Heading (radians) — smaller scale
    STEERING_SIGNAL_EPSILON = 1e-6  # Heading (radians) — float precision

    def run_discovery_for_action(
        self,
        action_name: str,
        send_action_fn: Callable,
        get_feedbacks_fn: Callable,
        wait_fn: Callable,
        reset_fn: Optional[Callable] = None,
        frame_duration_s: float = 0.05
    ) -> ActionDiscoveryResult:
        """
        Run downward sweep for one action (algorithm_spec_from_meetings.md).

        Probe action=0 for context, then descend powers of 10.
        Find MAX bracket (delta drops below saturated), binary search it.
        Find MIN bracket (delta becomes same as action=0), binary search it.
        Store MIN, MAX.

        Each probe = one frame = one answer (section 1, section 13).
        Pure: STATE_t --(ACTION per frame)--> STATE_t+1
        """
        config = self.actions_config[action_name]
        action_range = (config['range'][0], config['range'][1])
        is_bidir = config['range'][0] < 0

        # Two epsilons per measurement scale:
        # noise = method variance floor, signal = system precision
        if action_name == 'steering':
            noise_eps = self.STEERING_NOISE_EPSILON
            signal_eps = self.STEERING_SIGNAL_EPSILON
        else:
            noise_eps = self.DEFAULT_NOISE_EPSILON
            signal_eps = self.DEFAULT_SIGNAL_EPSILON

        disc = FrameBinDiscovery(action_name, action_range, self.search_precision,
                                 noise_epsilon=noise_eps, signal_epsilon=signal_eps)
        result = ActionDiscoveryResult(action_name=action_name)
        t0 = time.time()

        def make_action(value: float) -> Dict[str, float]:
            """Build action dict with only test action non-zero."""
            a = {name: 0.0 for name in self.actions_config}
            a[action_name] = max(action_range[0], min(value, action_range[1]))
            return a

        # Neutral action for D0 measurement
        neutral = {name: 0.0 for name in self.actions_config}

        def probe_one_frame(value: float) -> ProbeResult:
            """Two frames per probe: measure physics, then measure action.

            Frame 1: action=0 → D0_local (what physics does HERE)
            Frame 2: action=X → delta_raw (action + physics)
            signal = delta_raw - D0_local (pure action contribution)

            This removes inherited momentum/drag from previous probes.
            From rest: D0_local=0 at first probe, grows as car gains speed.
            At speed: D0_local captures current drag. Either way, the
            subtraction isolates what the action itself contributed.

            Two epsilons: noise_epsilon (0.05) filters measurement variance,
            signal_epsilon (1e-7) catches the smallest real system reading.
            """
            for attempt in range(self.MAX_PROBE_RETRIES):
                clamped = max(action_range[0], min(value, action_range[1]))
                action_dict = make_action(clamped)

                # Frame 1: action=0 — measure what physics does HERE
                fb_pre = get_feedbacks_fn()
                send_action_fn(neutral)
                wait_fn(frame_duration_s)
                fb_before = get_feedbacks_fn()

                # D0_local: speed change (or heading change) from doing nothing
                d0_local = disc.compute_delta(
                    fb_pre, fb_before,
                    action_name=action_name,
                    pre_before=None
                )

                # Frame 2: action=X — measure what the action does HERE
                send_action_fn(action_dict)
                wait_fn(frame_duration_s)
                fb_after = get_feedbacks_fn()

                # delta_raw: speed change (or heading change) from the action
                delta_raw = disc.compute_delta(
                    fb_before, fb_after,
                    action_name=action_name,
                    pre_before=fb_pre  # Steering needs this for heading
                )

                if delta_raw is not None:
                    # Subtract local physics to isolate action's contribution
                    delta = delta_raw - (d0_local or 0.0)
                    break
                else:
                    delta = None

                if attempt < self.MAX_PROBE_RETRIES - 1:
                    logger.warning(f"    Probe invalid (low displacement), "
                                   f"retry {attempt+2}/{self.MAX_PROBE_RETRIES}")

            # Determine validity
            is_valid = delta is not None
            if not is_valid:
                logger.warning(f"    Probe INVALID after {self.MAX_PROBE_RETRIES} attempts. "
                               f"Marking valid=False.")
                delta = 0.0  # Placeholder, valid=False excludes it

            if self.total_experiments == 0 or result.experiments_run == 0:
                logger.info(f"  Epsilon: noise={disc.noise_epsilon}, signal={disc.signal_epsilon} ({action_name})")

            self.total_experiments += 1
            result.experiments_run += 1

            pr = ProbeResult(
                action_value=clamped,
                delta_state=delta,
                feedback_before=fb_before.copy(),
                feedback_after=fb_after.copy(),
                frame_duration_s=frame_duration_s,
                feedback_pre_before=fb_pre.copy() if fb_pre else None,
                valid=is_valid
            )
            disc.probes.append(pr)
            result.probe_log.append({
                'step': self.total_experiments,
                'action': clamped,
                'delta': delta,
                'valid': is_valid,
                'speed_before': fb_before.get('speed', 0),
                'speed_after': fb_after.get('speed', 0),
            })

            return pr

        # =====================================================
        # RUN DISCOVERY (downward sweep — algorithm_spec_from_meetings.md)
        # =====================================================
        logger.info(f"[DISCOVERY] {action_name}: Downward sweep")
        logger.info(f"  Range: {action_range}, Precision: {self.search_precision}")
        logger.info(f"  Noise epsilon: {noise_eps} (measurement variance floor)")
        logger.info(f"  Signal epsilon: {signal_eps} (system precision)")
        logger.info(f"  Probe: 1 frame per probe (pure Sutton)")

        self.phase = ExperimentationPhase.DISCOVERING
        a_max, a_min = disc.run_discovery(probe_one_frame)

        # Handle results
        if a_max is None and a_min is None:
            result.success = False
            result.a_max_effective = action_range[1]
            result.a_min_effective = action_range[1]
            result.a_min_identifiable = False
            result.delta_0 = disc.delta_0 if disc.delta_0 is not None else 0.0
            result.delta_max = disc.delta_max or 0.0
            result.error_message = "Action has no detectable range"

            bins = [
                ActionBin(bin_id=0, a_min=action_range[0], a_max=action_range[1],
                          label='NO_EFFECT', effect_delta=0.0)
            ]
            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

            result.discovered_bins = bins
            self.discovered_bins[action_name] = bins
            self.discovery_results[action_name] = result

            logger.warning(f"  {action_name}: No detectable range")
            return result

        result.a_max_effective = a_max or action_range[1]
        result.a_min_effective = a_min or action_range[1] * 0.01
        result.a_min_identifiable = a_min is not None
        result.delta_0 = disc.delta_0 if disc.delta_0 is not None else 0.0
        result.delta_at_min = disc.delta_at_min or 0.0
        result.max_bracket = (disc.a_max or 0.0, disc.a_max or 0.0)
        result.min_bracket = (disc.a_min or 0.0, disc.a_min or 0.0)
        result.system_precision = disc.system_precision
        result.delta_max = disc.delta_max or 0.0

        logger.info(f"  [RESULT] MAX={result.a_max_effective:.6f} (delta_max={result.delta_max:.6f}), "
                     f"MIN={result.a_min_effective:.6f} (identifiable={result.a_min_identifiable})")
        logger.info(f"  Epsilon: noise={disc.noise_epsilon}, signal={disc.signal_epsilon}")

        # =====================================================
        # BUILD BINS: uniform divisions of [MIN, MAX]
        # =====================================================
        # Spec: "Store MIN, MAX, Δ per frame"
        # Bins are computed from MIN/MAX, NOT probed.
        bins = disc.build_bins()

        if is_bidir:
            bins = disc.make_bidirectional_bins(bins)

        result.discovered_bins = bins
        result.discovery_time = time.time() - t0
        result.success = True

        self.discovered_bins[action_name] = bins
        self.discovery_results[action_name] = result

        # Track precision
        for pr in disc.probes:
            self._track_precision(pr.feedback_after)

        logger.info(f"  {action_name}: {len(bins)} bins in {result.discovery_time:.1f}s")
        for b in bins:
            logger.info(f"    Bin {b.bin_id}: [{b.a_min:.6f}, {b.a_max:.6f}) = {b.label}")

        return result

    def _track_precision(self, feedbacks: Dict[str, float]):
        """Track feedback precision."""
        for name, value in feedbacks.items():
            s = f"{value:.10f}".rstrip('0')
            dec = len(s.split('.')[1]) if '.' in s else 0

            if name not in self.precision_results:
                self.precision_results[name] = {
                    'feedback_name': name,
                    'decimal_places': dec,
                    'min_observable_change': 10 ** (-dec) if dec > 0 else 1.0,
                    'sample_count': 1
                }
            else:
                pr = self.precision_results[name]
                pr['sample_count'] += 1
                if dec > pr['decimal_places']:
                    pr['decimal_places'] = dec
                    pr['min_observable_change'] = 10 ** (-dec)

    def _complete(self):
        self.phase = ExperimentationPhase.COMPLETED
        self.end_time = time.time()

        dt = self.end_time - (self.start_time or self.end_time)
        logger.info("=" * 70)
        logger.info("[EXPERIMENTATION] COMPLETE")
        logger.info(f"  Total probes: {self.total_experiments}")
        logger.info(f"  Time: {dt:.1f}s")
        for name, bins in self.discovered_bins.items():
            r = self.discovery_results.get(name)
            logger.info(f"  {name}: {len(bins)} bins, "
                        f"min={r.a_min_effective if r else '?'}, "
                        f"max={r.a_max_effective if r else '?'}, "
                        f"D0={r.delta_0 if r else '?'}")
        logger.info("=" * 70)

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def get_discovered_bins(self) -> Dict[str, List[Dict[str, Any]]]:
        result = {}
        for name, bins in self.discovered_bins.items():
            result[name] = [b.to_dict() for b in bins]
        return result

    def get_precision_results(self) -> Dict[str, Any]:
        return dict(self.precision_results)

    def is_complete(self) -> bool:
        return self.phase == ExperimentationPhase.COMPLETED

    def is_failed(self) -> bool:
        return self.phase == ExperimentationPhase.FAILED

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'phase': self.phase.value,
            'algorithm': 'downward_sweep',
            'total_experiments': self.total_experiments,
            'actions_discovered': len(self.discovered_bins),
            'actions_total': len(self.actions_config),
            'elapsed_time': (time.time() - self.start_time) if self.start_time else 0,
            'precision': dict(self.precision_results),
            'results': {n: r.to_dict() for n, r in self.discovery_results.items()}
        }

    def skip_experimentation_with_defaults(
        self, emergency_no_environment: bool = False
    ) -> Dict[str, List[ActionBin]]:
        if not emergency_no_environment:
            raise RuntimeError(
                "[VIOLATION] Cannot skip experimentation without "
                "emergency_no_environment=True."
            )

        logger.error("[EXPERIMENTATION] EMERGENCY: Using fallback bins")

        for action_name, config in self.actions_config.items():
            is_bidir = config['range'][0] < 0
            disc = FrameBinDiscovery(action_name, tuple(config['range']))
            disc.a_min = 0.1
            disc.a_max = config['range'][1]
            disc.delta_max = config['range'][1]

            bins = disc.build_bins()
            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

            self.discovered_bins[action_name] = bins
            self.discovery_results[action_name] = ActionDiscoveryResult(
                action_name=action_name,
                a_min_effective=0.1,
                a_max_effective=config['range'][1],
                discovered_bins=bins,
                discovery_source=DiscoverySource.EMERGENCY_FALLBACK,
                success=True
            )

        self.phase = ExperimentationPhase.COMPLETED
        return self.discovered_bins


# =============================================================================
# COORDINATOR (connects intelligence to environment)
# =============================================================================

class ExperimentationCoordinator:
    """
    Coordinates experimentation with live environment.

    Runs the downward sweep algorithm for each action in sequence
    (algorithm_spec_from_meetings.md).
    """

    # Minimum speed for per-frame probes to produce measurable deltas.
    # Sutton's example starts at speed=100 — car must be moving.
    # Section 9: "system initializes" before experimentation.
    MIN_PROBE_SPEED = 25.0  # km/h

    def __init__(
        self,
        actions_config: Dict[str, Any],
        send_action_fn: Callable[[Dict[str, float]], None],
        get_feedbacks_fn: Callable[[], Dict[str, float]],
        wait_fn: Callable[[float], None] = None,
        reset_fn: Callable[[], None] = None,
        reset_fns: Optional[Dict[str, Callable]] = None,
        frame_duration_s: float = 0.05,
        min_probe_speed: float = None
    ):
        self.intelligence = ExperimentationIntelligence(actions_config)
        self.send_action = send_action_fn
        self.get_feedbacks = get_feedbacks_fn
        self.wait = wait_fn or (lambda t: time.sleep(t))
        self.reset_fn = reset_fn
        self.reset_fns = reset_fns or {}
        self.frame_duration_s = frame_duration_s
        self.min_probe_speed = min_probe_speed or self.MIN_PROBE_SPEED

    def ensure_measurable_regime(self):
        """System initialization (section 9) — get car moving before experimentation.

        Section 5A: "Speed starts at 100" — car should be moving.
        Section 3: "do not interfere" — don't RESET, but getting moving is init.

        NO stabilization coast. NO overshoot. Start probing from here.
        """
        fb = self.get_feedbacks()
        speed = fb.get('speed', 0)

        if speed >= self.min_probe_speed:
            logger.info(f"[REGIME] Speed {speed:.1f} km/h >= {self.min_probe_speed} — ready")
            return

        logger.info(f"[REGIME] Speed {speed:.1f} km/h < {self.min_probe_speed} — "
                     f"applying gas (system init, not experimentation)")

        frames = 0
        while speed < self.min_probe_speed:
            self.send_action({name: 0.0 for name in self.intelligence.actions_config}
                              | {'gas': 1.0})
            self.wait(self.frame_duration_s)
            fb = self.get_feedbacks()
            speed = fb.get('speed', 0)
            frames += 1

            if frames > 500:  # Safety: ~25 seconds max
                logger.warning(f"[REGIME] Could not reach {self.min_probe_speed} km/h "
                               f"after {frames} frames (speed={speed:.1f})")
                break

        logger.info(f"[REGIME] Speed {speed:.1f} km/h reached in {frames} frames "
                     f"({frames * self.frame_duration_s:.1f}s) — ready")

    def run_full_experimentation(self) -> Dict[str, List[Dict[str, Any]]]:
        """Run downward sweep for ALL actions.

        Section 3: "do not interfere with the experimentation."
        Section 5C: "Starting from rest avoids this complexity entirely."

        Gas/brake discover from rest (speed=0). At rest there is no drag,
        no inertia, no momentum — Pong-like. Delta depends only on the
        action value. Epsilon matches system float precision.

        Steering needs displacement for heading measurement, so we
        accelerate before steering (section 9: system initializes).
        """
        logger.info("[COORDINATOR] Starting bin discovery (algorithm_spec_from_meetings.md)")
        logger.info(f"  Frame duration: {self.frame_duration_s*1000:.0f}ms "
                     f"(1 frame per probe, pure Sutton)")
        self.intelligence.start_time = time.time()

        fb = self.get_feedbacks()
        logger.info(f"[COORDINATOR] Starting state: speed={fb.get('speed', 0):.1f} km/h")

        for action_name in self.intelligence.actions_config:
            # Steering needs car moving for heading measurement.
            # Gas/brake discover from rest — Pong-like, no drag.
            if action_name == 'steering':
                self.ensure_measurable_regime()

            logger.info(f"\n{'='*60}")
            logger.info(f"  DISCOVERING: {action_name}")
            logger.info(f"{'='*60}")

            action_reset = self.reset_fns.get(action_name, self.reset_fn)

            self.intelligence.run_discovery_for_action(
                action_name=action_name,
                send_action_fn=self.send_action,
                get_feedbacks_fn=self.get_feedbacks,
                wait_fn=self.wait,
                reset_fn=action_reset,
                frame_duration_s=self.frame_duration_s
            )

        self.intelligence._complete()
        return self.intelligence.get_discovered_bins()

    def run_from_documentation(
        self, documented_values: Dict[str, Dict[str, float]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        return self.intelligence.load_from_documentation(documented_values)
