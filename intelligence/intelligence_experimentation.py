"""
INTELLIGENCE: Experimentation - discovery's Exact Bin Discovery Algorithm

AUTHORITATIVE LAW (from experimentation_algorithm.md):

    FOR each action type:

        1. Measure D0 = step(action=0)

        2. Find bracket for MAX:
                large value -> saturated?
                shrink until bracket found

        3. Binary search bracket
                until precision reached

        4. Find bracket for MIN:
                find first value != D0

        5. Binary search for boundary

        6. Store:
                MIN
                MAX
                D per frame

CORE PRINCIPLES (non-negotiable):

    - No noise. No delay. No seconds. No averaging.
    - Everything is: STATE_t --(ACTION per frame)--> STATE_t+1
    - Action=0 is also an action (NOT noise, NOT baseline to subtract)
    - Frame is the atomic time unit
    - "Not doing an action is also an action" - discovery
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
    MEASURING_DELTA0 = "measuring_delta0"
    DISCOVERING_MAX = "discovering_max"
    DISCOVERING_MIN = "discovering_min"
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
# SUTTON'S EXACT BIN DISCOVERY (per-action)
# =============================================================================

class FrameBinDiscovery:
    """
    discovery's exact bin discovery algorithm for a single action.

    The algorithm:
        1. Measure D0 = step(action=0) -- one frame, one measurement
        2. Exponential bracketing for MAX (descend powers of 10)
        3. Binary search bracket for MAX
        4. Exponential descent for MIN (find where delta == D0)
        5. Binary search for MIN boundary
        6. Store MIN, MAX

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
        search_precision: float = None,
        measurement_epsilon: float = None
    ):
        """
        Initialize bin discovery for a single action.

        Sutton: "bins needs to be figured out by the system. Not by us."
        Sutton: "the precision is not us, precision is the system."

        No hardcoded ranges, no hardcoded epsilons. Everything is either
        discovered from the environment or passed in after measurement.

        Args:
            action_name: Name of the action (e.g., 'gas', 'brake', 'left')
            search_precision: Binary search convergence threshold.
                MUST be discovered from the environment (repeated D0 probes).
                If None, binary search uses a 50-step safety limit only.
            measurement_epsilon: Delta comparison threshold.
                MUST be discovered from the environment (D0 probe variance).
                If None, uses bit-exact comparison (any difference is real).
        """
        self.action_name = action_name
        self.search_precision = search_precision
        self.measurement_epsilon = measurement_epsilon

        # Core results
        self.delta_0: Optional[float] = None      # Delta when action=0 (real transition)
        self.delta_max: Optional[float] = None     # Saturated delta
        self.a_max: Optional[float] = None         # Discovered MAX
        self.a_min: Optional[float] = None         # Discovered MIN
        self.delta_at_min: Optional[float] = None  # Delta at MIN
        self.nature: Optional[str] = None          # 'binary', 'analog', or 'none' (discovered)

        # Probe history
        self.probes: List[ProbeResult] = []
        self.system_precision: int = 0  # Discovered from feedback

    # -----------------------------------------------------------------
    # DELTA COMPUTATION: SIGNED, not absolute
    # -----------------------------------------------------------------

    # Minimum displacement for valid heading measurement
    STEERING_MIN_DISPLACEMENT = 0.1

    def compute_delta(self, before: Dict[str, float], after: Dict[str, float],
                      action_name: str = None,
                      pre_before: Dict[str, float] = None) -> Optional[float]:
        """SIGNED state change: after - before.

        discovery: "STATE_t --(ACTION per frame)--> STATE_t+1"
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
        """Are two deltas the same within discovered measurement precision?

        Sutton Jan 24: "the precision is not us, precision is the system."

        If measurement_epsilon was discovered (from repeated D0 probes),
        use it. If not discovered, use bit-exact comparison —
        with deterministic rewind, any difference is real signal.
        """
        if self.measurement_epsilon is not None and self.measurement_epsilon > 0:
            return abs(d1 - d2) < self.measurement_epsilon
        # No epsilon discovered → bit-exact comparison
        return d1 == d2

    def _is_saturated(self, delta: float) -> bool:
        """Is this delta the same as the saturated (max) delta?

        discovery: "if you go beyond the max the delta won't change"
        """
        if self.delta_max is None:
            return False
        return self._deltas_are_same(delta, self.delta_max)

    def _is_same_as_delta0(self, delta: float) -> bool:
        """Is this delta the same as D0 (action=0)?

        Sutton: "not doing an action is also an action."
        If delta == D0, the tested action had no effect beyond coasting.
        """
        if self.delta_0 is None:
            return delta == 0.0  # Before D0 is measured, assume 0
        return self._deltas_are_same(delta, self.delta_0)

    # -----------------------------------------------------------------
    # PRECISION TRACKING
    # -----------------------------------------------------------------

    def update_precision(self, feedbacks: Dict[str, float], action_name: str = None):
        """No-op. Epsilon is now calibrated empirically, not from string formatting."""
        pass

    # -----------------------------------------------------------------
    # STEP 1: MEASURE D0
    # -----------------------------------------------------------------

    def get_exponential_sequence(self) -> List[float]:
        """Descending powers of 10 from 1e6 down to 1e-6.

        Sutton Jan 15: "you start with zero and then you go to like 0.1
        0.01 0.001... it's a power of 10"

        Sutton Feb 16 (Pong example): "start at 100 for the pong"
        Algorithm spec: "Start at large value (1e6)"

        The sequence starts LARGE so the algorithm discovers the action
        range rather than assuming it. No hardcoded ranges.

        Returns: [1e6, 1e5, 1e4, 1e3, 100, 10, 1, 0.1, 0.01, ..., 1e-6]
        """
        values = []
        exp = 6   # Start at 10^6
        while exp >= -6:
            values.append(10.0 ** exp)
            exp -= 1
        return values

    # -----------------------------------------------------------------
    # NATURE DETECTION: Binary vs Analog (two-stage model)
    # -----------------------------------------------------------------

    # Legacy fallback — prefer wire_precision-derived probes
    NATURE_PROBE_VALUES = [1e-6, 0.001, 1.0, 1000.0]

    def detect_action_nature(
        self,
        probe_fn: Callable[[float], 'ProbeResult'],
        wire_precision: dict = None
    ) -> str:
        """Detect whether action is BINARY or ANALOG before full sweep.

        Probes are DERIVED from wire precision when available
        (Sutton: "first find the system's precision").
        When wire_precision is provided, probes span from float_max down to
        float_step in powers of 10. When not provided, falls back to
        hardcoded NATURE_PROBE_VALUES for backward compatibility.

        Detection method (from multi-speed binary proof):
          1. Measure D0 = probe_fn(0.0)
          2. Probe values spanning multiple orders of magnitude
          3. Collect deltas, excluding any that equal D0 (dead zone probes)
          4. If ALL non-D0 deltas are identical (within measurement_epsilon)
             -> BINARY (no transition region exists)
          5. If fewer than 2 non-D0 deltas found -> 'none' (no detectable effect)
          6. If deltas differ -> ANALOG (proceed with Sutton's full sweep)

        Side effects:
          - Sets self.delta_0 from the D0 probe
          - Sets self.delta_max from the first active probe
          - Adds all probes to self.probes (counted toward total_experiments)
          - Stores derived probes as self._nature_probes for reuse

        Returns: 'binary', 'analog', or 'none'
        """
        # Derive probes from wire precision (Sutton: "first find the system's precision")
        if wire_precision:
            float_max = wire_precision['float_max']
            float_step = wire_precision['float_step']
            probes = []
            val = float_max
            while val >= float_step:
                probes.append(val)
                val /= 10.0
            probes.append(float_step)  # smallest wire can represent
            # Deduplicate and sort descending
            probes = sorted(set(probes), reverse=True)
        else:
            probes = list(self.NATURE_PROBE_VALUES)  # fallback

        # Store for reuse by _run_binary_discovery and analog path
        self._nature_probes = probes

        logger.info(f"  [NATURE DETECTION] Probing {len(probes)} "
                     f"values to detect binary vs analog..."
                     + (f" (derived from wire precision)" if wire_precision else ""))

        # Step 1: Measure D0
        logger.info(f"  [STEP 1] Measure D0 = step(action=0)")
        d0_probe = probe_fn(0.0)
        if d0_probe not in self.probes:
            self.probes.append(d0_probe)
        if d0_probe.valid:
            self.delta_0 = d0_probe.delta_state
        else:
            self.delta_0 = 0.0
            logger.warning(f"    D0 probe invalid, using 0.0")
        logger.info(f"    D0 = {self.delta_0:.6f}")
        logger.info(f"    (Real transition, not noise)")

        # Step 2: Probe across orders of magnitude
        active_deltas = []  # Deltas that differ from D0
        nature_probes = []  # (value, delta) pairs for all probes

        for val in probes:
            pr = probe_fn(val)
            if pr not in self.probes:
                self.probes.append(pr)
            if not pr.valid:
                logger.info(f"    nature probe a={val:.6g} -> INVALID (skipped)")
                continue

            delta = pr.delta_state
            nature_probes.append((val, delta))
            logger.info(f"    nature probe a={val:.6g} -> delta={delta:.10g}")

            if not self._is_same_as_delta0(delta):
                active_deltas.append(delta)
                # First active probe sets delta_max (saturated reference)
                if self.delta_max is None:
                    self.delta_max = delta

        # Step 3: Classify
        if len(active_deltas) < 2:
            # Fewer than 2 non-D0 deltas: action has no detectable effect
            # or only one magnitude works
            self.nature = 'none'
            logger.info(f"  [NATURE] = NONE (only {len(active_deltas)} active probes)")
            return 'none'

        # Check if ALL active deltas are identical (within epsilon)
        ref_delta = active_deltas[0]
        all_same = all(self._deltas_are_same(d, ref_delta) for d in active_deltas[1:])

        if all_same:
            self.nature = 'binary'
            self.delta_max = ref_delta
            logger.info(f"  [NATURE] = BINARY")
            logger.info(f"    All {len(active_deltas)} active probes produce identical "
                         f"delta = {ref_delta:.10g}")
            logger.info(f"    No transition region exists. Action is digital on/off.")
        else:
            self.nature = 'analog'
            logger.info(f"  [NATURE] = ANALOG")
            logger.info(f"    Deltas differ across magnitudes -> transition region exists.")
            logger.info(f"    Proceeding with Sutton's full exponential sweep + binary search.")

        return self.nature

    def _run_binary_discovery(
        self,
        probe_fn: Callable[[float], 'ProbeResult'],
        wire_precision: dict = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """Binary action discovery: find meaningful MIN via binary search.

        For binary actions, all values above some threshold produce the
        same delta. There is no transition region, so Sutton's full
        exponential sweep would waste probes finding nothing.

        Instead:
          1. MAX = 1.0 (the nominal full-scale value, validated by probing)
          2. MIN = discovered via binary search between smallest active probe
             and 0.0 (where delta transitions from D0 to active)
          3. bins = 2 (dead zone + active)

        When wire_precision is provided, the MIN binary search stops at the
        wire step boundary (e.g., 1/255 for uint8) instead of grinding down
        to floating-point epsilon.

        The nature detection probes already confirmed binary behavior.
        Now we just need to validate MAX and find true MIN.
        """
        logger.info(f"  [BINARY PATH] Finding meaningful boundaries...")

        # Wire step floor: stop binary search at wire resolution limit
        wire_step = wire_precision['float_step'] if wire_precision else None
        saved_search_precision = self.search_precision
        if wire_step is not None:
            effective_precision = max(self.search_precision or 0, wire_step)
            self.search_precision = effective_precision
            logger.info(f"    Wire step floor: {wire_step:.6g} "
                        f"(search_precision set to {effective_precision:.6g})")

        # Validate MAX = 1.0
        # Binary actions: any value above threshold = same effect.
        # 1.0 is the nominal full-scale value. Confirm it produces delta_max.
        pr_max = probe_fn(1.0)
        if pr_max.valid and self._deltas_are_same(pr_max.delta_state, self.delta_max):
            self.a_max = 1.0
            logger.info(f"    MAX = 1.0 (validated: delta={pr_max.delta_state:.10g} "
                         f"matches delta_max={self.delta_max:.10g})")
        else:
            # Unexpected: 1.0 doesn't produce saturated delta.
            # Fall back to the largest nature probe that was active.
            for val in reversed(sorted(v for v, d in
                    [(nv, nd) for nv, nd in
                     [(p.action_value, p.delta_state) for p in self.probes
                      if p.action_value > 0 and p.valid]]
                    if not self._is_same_as_delta0(d))):
                self.a_max = val
                break
            else:
                self.a_max = 1.0  # Default if somehow no active probes
            logger.warning(f"    MAX = {self.a_max} (1.0 did not match delta_max, "
                           f"using largest active probe)")

        # Find MIN via binary search
        # We know from nature probes which values are active (differ from D0)
        # and which are in the dead zone (same as D0).
        # For TMNF binary inputs, the threshold is at the adapter level
        # (any float > 0.0 activates the key), so MIN may be extremely small.

        # Find the smallest nature probe value that was still active
        # Use self._nature_probes (derived from wire precision when available)
        nature_probes = getattr(self, '_nature_probes', self.NATURE_PROBE_VALUES)
        smallest_active = None
        for val in sorted(nature_probes):
            pr_check = None
            for p in self.probes:
                if p.action_value == val and p.valid:
                    pr_check = p
                    break
            if pr_check and not self._is_same_as_delta0(pr_check.delta_state):
                smallest_active = val
                break

        if smallest_active is None:
            # All probes were dead zone somehow (shouldn't happen if nature='binary')
            self.a_min = nature_probes[0] if nature_probes else 1e-6
            logger.warning(f"    MIN = {self.a_min} (no active probes found in nature detection)")
        elif smallest_active == sorted(nature_probes)[0]:
            # Even the smallest probe (1e-6) was active.
            # The true MIN is below our tested range.
            # Try even smaller values to find where delta transitions to D0.
            logger.info(f"    Smallest nature probe ({smallest_active:.6g}) still active.")
            logger.info(f"    Probing below {smallest_active:.6g} for true MIN...")

            # Probe progressively smaller values
            test_below = [smallest_active * 0.001, smallest_active * 1e-6, 0.0]
            found_d0_at = None
            last_active = smallest_active

            for tv in test_below:
                if tv <= 0.0:
                    # Zero = D0 by definition
                    found_d0_at = 0.0
                    break
                pr_tv = probe_fn(tv)
                if pr_tv.valid:
                    if self._is_same_as_delta0(pr_tv.delta_state):
                        found_d0_at = tv
                        logger.info(f"      a={tv:.6g} -> D0 (dead zone)")
                        break
                    else:
                        last_active = tv
                        logger.info(f"      a={tv:.6g} -> active (delta={pr_tv.delta_state:.10g})")

            if found_d0_at is not None and found_d0_at < last_active:
                # Binary search between found_d0_at and last_active
                logger.info(f"    Binary search for MIN in [{found_d0_at:.6g}, {last_active:.6g}]")
                self.a_min, bs_steps = self._binary_search_min(
                    probe_fn, found_d0_at, last_active
                )
                logger.info(f"    >>> MIN = {self.a_min:.10g} ({bs_steps} binary search steps)")
            else:
                # Even 1e-12 is still active -- MIN is at the adapter boundary
                self.a_min = last_active
                logger.info(f"    MIN = {self.a_min:.6g} (smallest tested value still active)")
                logger.info(f"    True threshold likely at adapter level (any float > 0.0)")
        else:
            # There's a dead zone probe below smallest_active
            # Find the largest dead zone probe
            largest_dead = 0.0
            for val in sorted(nature_probes):
                if val >= smallest_active:
                    break
                pr_check = None
                for p in self.probes:
                    if p.action_value == val and p.valid:
                        pr_check = p
                        break
                if pr_check and self._is_same_as_delta0(pr_check.delta_state):
                    largest_dead = val

            logger.info(f"    Binary search for MIN in [{largest_dead:.6g}, {smallest_active:.6g}]")
            self.a_min, bs_steps = self._binary_search_min(
                probe_fn, largest_dead, smallest_active
            )
            logger.info(f"    >>> MIN = {self.a_min:.10g} ({bs_steps} binary search steps)")

        # Record delta_at_min
        pr_min = probe_fn(self.a_min)
        self.delta_at_min = pr_min.delta_state if pr_min.valid else self.delta_max

        # Restore original search_precision (may have been overridden by wire_step)
        self.search_precision = saved_search_precision

        logger.info(f"  [BINARY PATH COMPLETE]")
        logger.info(f"    MAX = {self.a_max}")
        logger.info(f"    MIN = {self.a_min:.10g}")
        logger.info(f"    delta_max = {self.delta_max:.10g}")
        logger.info(f"    delta_at_min = {self.delta_at_min:.10g}")
        logger.info(f"    bins = 2 (dead zone + active)")

        return self.a_max, self.a_min

    # -----------------------------------------------------------------
    # STEPS 2-5: FULL DISCOVERY
    # -----------------------------------------------------------------

    def run_discovery(
        self,
        probe_fn: Callable[[float], ProbeResult],
        wire_precision: dict = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Two-stage discovery: detect action nature, then apply appropriate algorithm.

        When wire_precision is provided (Sutton: "first find the system's precision"),
        probe values are DERIVED from the wire format instead of using hardcoded
        NATURE_PROBE_VALUES, and MIN search stops at the wire step boundary.

        Stage 1: Nature Detection (detect_action_nature)
            Probe values spanning multiple orders of magnitude.
            If ALL non-D0 deltas identical -> BINARY
            If deltas differ -> ANALOG

        Stage 2A: Binary path (_run_binary_discovery)
            MAX = 1.0 (validated), MIN via binary search. ~6-8 probes total.

        Stage 2B: Analog path (Sutton's full algorithm)
            1. Measure D0 = step(action=0)  [already done in Stage 1]
            2. Find bracket for MAX: large value -> saturated? shrink until bracket found
            3. Binary search bracket until precision reached
            4. Find bracket for MIN: find first value == D0
            5. Binary search for boundary
            6. Store: MIN, MAX, D per frame

        No heuristics. No baseline subtraction. No magic decimals.
        Pure transition search.

        Sutton: "Not doing an action is also an action."
        D0 is a REAL transition, not noise to be subtracted.

        The nature detection probes count toward total experiments.
        Binary detection is DISCOVERED, not hardcoded.

        Args:
            probe_fn: Function that probes a single action value and returns ProbeResult.
            wire_precision: Optional dict with wire format metadata from adapter.
                Keys: wire_type, wire_bits, wire_min, wire_max,
                      float_min, float_max, float_step.

        Returns:
            (a_max, a_min) or (None, None) if action has no effect.
        """
        # ===========================================
        # STAGE 1: Detect action nature (binary vs analog)
        # ===========================================
        nature = self.detect_action_nature(probe_fn, wire_precision=wire_precision)

        if nature == 'none':
            logger.warning(f"  Action has no detectable effect.")
            return None, None

        if nature == 'binary':
            return self._run_binary_discovery(probe_fn, wire_precision=wire_precision)

        # ===========================================
        # STAGE 2B: ANALOG PATH -- Sutton's full algorithm
        # D0 already measured by detect_action_nature.
        # For the analog path, we reset delta_max so the exponential
        # sweep re-establishes it from the LARGEST probe value (1e6),
        # which is the true saturated delta for analog actions.
        # ===========================================
        sequence = self.get_exponential_sequence()
        self.delta_max = None  # Reset so exponential sweep re-discovers from largest value

        # ===========================================
        # STEP 2: Exponential bracketing for MAX
        # Sutton: "large value -> saturated? shrink until bracket found"
        # Then continue descent for MIN: "find first value == D0"
        # ===========================================
        logger.info(f"  [STEP 2] Exponential bracketing (analog path)...")

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

            # First valid probe = saturated delta (highest action value)
            if self.delta_max is None:
                self.delta_max = delta
                logger.info(f"    (saturated delta = {delta:.6f})")
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
            # discovery: "find first value == D0" (action has no effect beyond coasting)
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

        # Edge case: never found MAX bracket (all probes saturated)
        # This means the action is BINARY: any positive value produces
        # the same saturated delta. MAX = first tested value (largest).
        if not found_max_bracket:
            self.a_max = sequence[0]  # Largest value tested
            logger.info(f"  All probes saturated → BINARY action. MAX = {self.a_max}")

            # If also no MIN bracket, every tested value had effect.
            # This happens with digital inputs (any value > 0.0 = ON).
            # Set MIN = smallest tested value. Binary detection in build_bins()
            # will see delta_at_min == delta_max (same effect for all values).
            if not found_min_bracket:
                self.a_min = sequence[-1]
                self.delta_at_min = self.delta_max  # All values produce same delta
                logger.info(f"  BINARY: no brackets found but delta_max != D0.")
                logger.info(f"  MIN = {self.a_min} (smallest tested, still had effect)")
                logger.info(f"  MAX = {self.a_max}, delta_at_min = delta_max = {self.delta_max:.6f}")
                return self.a_max, self.a_min

        # ===========================================
        # STEP 3: Binary search for MAX
        # Sutton: "Binary search bracket until precision reached"
        # ===========================================
        if found_max_bracket:
            logger.info(
                f"  [STEP 3] Binary search for MAX in "
                f"[{max_bracket_low:.6f}, {max_bracket_high:.6f}]..."
            )
            self.a_max, bs_steps = self._binary_search_max(
                probe_fn, max_bracket_low, max_bracket_high
            )
            logger.info(f"    >>> MAX = {self.a_max:.6f} ({bs_steps} binary search steps)")

        # ===========================================
        # STEP 4-5: Binary search for MIN
        # discovery: "find first value != D0" then "binary search for boundary"
        # Uses D0 comparison: delta == D0 means no effect.
        # ===========================================
        if found_min_bracket:
            logger.info(
                f"  [STEP 4-5] Binary search for MIN in "
                f"[{min_bracket_low:.6f}, {min_bracket_high:.6f}]..."
            )
            self.a_min, bs_steps = self._binary_search_min(
                probe_fn, min_bracket_low, min_bracket_high
            )
            logger.info(f"    >>> MIN = {self.a_min:.6f} ({bs_steps} binary search steps)")

            # Probe at MIN to record delta_at_min (used for binary detection)
            pr_min = probe_fn(self.a_min)
            self.delta_at_min = pr_min.delta_state
        else:
            if found_max_bracket:
                self.a_min = sequence[-1]
                logger.warning(
                    f"  MIN not bracketed (delta kept changing). "
                    f"Using smallest test value: {self.a_min:.6f}"
                )
            else:
                # All probes saturated AND delta_max == D0
                # (handled above, but safety fallback)
                return None, None

        # D0 already measured in Step 1 — stored in self.delta_0

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

        discovery example:
            [10, 100] -> mid=55(sat) -> [10,55] -> mid=32(sat) -> [10,32]
            -> mid=21(sat) -> [10,21] -> mid=15(not) -> [15,21]
            -> mid=18(sat) -> [15,18] -> mid=16(not) -> [16,18]
            -> mid=17(sat) -> [16,17] -> STOP
            MAX = 17
        """
        steps = 0
        max_steps = 50  # Safety limit
        while steps < max_steps:
            # Stop condition: bracket narrower than discovered precision
            if self.search_precision is not None and (high - low) <= self.search_precision:
                break
            mid = (low + high) / 2.0
            if mid == low or mid == high:
                break  # Float precision exhausted
            pr = probe_fn(mid)
            steps += 1

            if self._is_saturated(pr.delta_state):
                high = mid  # Still saturated, MAX might be lower
                logger.info(f"    [{low:.10g}, {high:.10g}] mid={mid:.10g} -> SATURATED")
            else:
                low = mid   # Not saturated, MAX is higher
                logger.info(f"    [{low:.10g}, {high:.10g}] mid={mid:.10g} -> not saturated")

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

        Sutton Feb 16 example:
            [1, 10] -> mid=5(same) -> [5,10] -> mid=7(diff) -> [5,7]
            -> mid=6(diff) -> [5,6] -> STOP
            MIN = 6
        """
        steps = 0
        max_steps = 50  # Safety limit
        while steps < max_steps:
            # Stop condition: bracket narrower than discovered precision
            if self.search_precision is not None and (high - low) <= self.search_precision:
                break
            mid = (low + high) / 2.0
            if mid == low or mid == high:
                break  # Float precision exhausted
            pr = probe_fn(mid)
            steps += 1

            if self._is_same_as_delta0(pr.delta_state):
                low = mid   # No effect at mid, MIN is higher
                logger.info(f"    [{low:.10g}, {high:.10g}] mid={mid:.10g} -> same as D0")
            else:
                high = mid  # Has effect at mid, MIN is lower or equal
                logger.info(f"    [{low:.10g}, {high:.10g}] mid={mid:.10g} -> different from D0")

        return high, steps  # MIN = smallest value with effect

    def _binary_search_min_consecutive(
        self,
        probe_fn: Callable[[float], ProbeResult],
        low: float,
        high: float
    ) -> Tuple[float, int]:
        """Binary search for MIN by comparing consecutive probes.

        Invariant: delta(low) SAME as delta(low_neighbor) → no effect
                   delta(high) DIFFERENT from delta(high_neighbor) → has effect
        MIN = smallest action where delta still differs from its neighbor.

        We probe mid and mid*0.5. If their deltas are same → no effect at mid,
        search higher. If different → has effect at mid, search lower.
        """
        steps = 0
        max_steps = 50
        while steps < max_steps:
            if self.search_precision is not None and (high - low) <= self.search_precision:
                break
            mid = (low + high) / 2.0
            if mid == low or mid == high:
                break
            pr_mid = probe_fn(mid)
            pr_half = probe_fn(mid * 0.5)
            steps += 2

            if self._deltas_are_same(pr_mid.delta_state, pr_half.delta_state):
                low = mid
                logger.info(f"    [{low:.10g}, {high:.10g}] mid={mid:.10g} -> same (dead zone)")
            else:
                high = mid
                logger.info(f"    [{low:.10g}, {high:.10g}] mid={mid:.10g} -> different (has effect)")

        return high, steps

    # -----------------------------------------------------------------
    # BIN BOUNDARY SEARCH: Binary search for where delta transitions
    # -----------------------------------------------------------------

    def search_bin_boundaries(
        self,
        probe_fn: Callable[[float], ProbeResult],
        max_depth: int = 8
    ) -> None:
        """Find bin boundaries by binary search for delta transitions.

        Same pattern as MAX/MIN discovery, applied to intermediate levels.
        Between consecutive search probes where delta differs, binary
        search for the exact transition point.

        This is NOT "sample then group". It's active boundary-finding
        using discovery's own binary search pattern.

        Discovered boundaries are stored in self.bin_boundaries.
        """
        if self.a_min is None or self.a_max is None:
            self.bin_boundaries: List[float] = []
            return

        # Collect valid probes in [MIN, MAX], sorted by action
        valid_probes = sorted(
            [p for p in self.probes if p.valid and self.a_min <= abs(p.action_value) <= self.a_max],
            key=lambda p: abs(p.action_value)
        )

        if len(valid_probes) < 2:
            self.bin_boundaries = []
            return

        boundaries: List[float] = []

        logger.info(f"  [BIN BOUNDARIES] Searching transitions in {len(valid_probes)} search probes...")

        # Find consecutive probe pairs where delta changes
        for i in range(len(valid_probes) - 1):
            p1 = valid_probes[i]
            p2 = valid_probes[i + 1]

            if not self._deltas_are_same(p1.delta_state, p2.delta_state):
                boundary = self._binary_search_transition(
                    probe_fn, abs(p1.action_value), abs(p2.action_value),
                    p1.delta_state, max_depth
                )
                if boundary is not None:
                    boundaries.append(boundary)
                    logger.info(f"    Boundary at a={boundary:.6f} "
                                 f"(between {abs(p1.action_value):.6f} and {abs(p2.action_value):.6f})")

        self.bin_boundaries = sorted(set(boundaries))
        logger.info(f"  [BIN BOUNDARIES] Found {len(self.bin_boundaries)} transition boundaries")

    def _binary_search_transition(
        self,
        probe_fn: Callable[[float], ProbeResult],
        low: float, high: float,
        delta_low: float,
        max_steps: int
    ) -> Optional[float]:
        """Binary search for where delta transitions between low and high."""
        for _ in range(max_steps):
            if self.search_precision is not None and (high - low) < self.search_precision:
                break
            mid = (low + high) / 2.0
            if mid == low or mid == high:
                break
            pr = probe_fn(mid)
            if not pr.valid:
                break
            if self._deltas_are_same(pr.delta_state, delta_low):
                low = mid
            else:
                high = mid
        return high

    # -----------------------------------------------------------------
    # BIN BUILDING: Uniform divisions of [MIN, MAX]
    # -----------------------------------------------------------------

    # Default number of bins between MIN and MAX
    DEFAULT_NUM_BINS = 10

    def build_bins(self, num_bins: int = None) -> List[ActionBin]:
        """Build bins as uniform divisions of [MIN, MAX].

        discovery: "Store MIN, MAX, Δ per frame"
        Bins are COMPUTED from MIN/MAX range, not probed individually.
        The planner uses these to discretize the action space.

        Structure:
            BIN 0: DEAD_ZONE [0, MIN)  — no effect beyond D0
            BIN 1..N: uniform [MIN, MAX] — active range
        """
        a_min = self.a_min or 0.01
        a_max = self.a_max or 1.0
        n = num_bins or self.DEFAULT_NUM_BINS

        bins: List[ActionBin] = []

        # Dead zone: [0, MIN) — action has no effect beyond D0
        bins.append(ActionBin(
            bin_id=0, a_min=0.0, a_max=a_min,
            label='DEAD_ZONE', effect_delta=self.delta_0 or 0.0
        ))

        # Binary detection:
        # With the two-stage model, binary actions are detected in
        # detect_action_nature() BEFORE the full sweep, giving meaningful
        # MIN/MAX (not 1e6/1e-6). This check remains as a safety net.
        # 1. MIN == MAX (trivially binary)
        # 2. Range < search_precision (threshold is narrower than precision)
        # 3. delta_at_min == delta_max (all action values produce same effect —
        #    digital input like TMNF keyboard keys, any positive = ON)
        is_binary = (
            a_min >= a_max or
            (self.search_precision is not None and (a_max - a_min) < self.search_precision) or
            (self.delta_at_min is not None and self.delta_max is not None and
             self._deltas_are_same(self.delta_at_min, self.delta_max))
        )
        if is_binary:
            bins.append(ActionBin(
                bin_id=1, a_min=a_min, a_max=a_max,
                label='BIN_1', effect_delta=self.delta_max or 0.0
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
    # BIDIRECTIONAL (steering) support
    # -----------------------------------------------------------------

    def make_bidirectional_bins(self, positive_bins: List[ActionBin]) -> List[ActionBin]:
        """Mirror positive bins for bidirectional action (steering [-1, +1]).

        discovery: "Same algorithm. Find smallest positive steering that changes
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
        """Clamp action to discovered [0, MAX] per frame.

        Sutton: "the max per frame is still the same... even if you want
        in one frame you cannot"
        """
        a_max = self.a_max or 1.0
        return max(0.0, min(value, a_max))


# =============================================================================
# EXPERIMENTATION INTELLIGENCE (orchestrates per-action discoveries)
# =============================================================================

class ExperimentationIntelligence:
    """
    Orchestrates bin discovery for all actions using discovery's exact algorithm.

    TWO PATHS:
    1. DOCUMENTATION: Known system -> load min/max/bins directly
    2. EXPERIMENTATION: Unknown system -> run discovery's algorithm
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

        logger.info("[EXPERIMENTATION] Initialized (discovery's exact algorithm)")
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

            a_min = values['min']
            a_max = values['max']

            disc = FrameBinDiscovery(action_name)
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
    # PATH 2: Experimentation (discovery's algorithm)
    # -----------------------------------------------------------------

    MAX_PROBE_RETRIES = 3          # Retries on invalid steering probe

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
        Run discovery's exact algorithm for one action.

        FOR this action (experimentation_algorithm.md):
            1. Measure D0 = step(action=0)
            2. Find bracket for MAX (exponential descent)
            3. Binary search for MAX
            4. Find bracket for MIN (exponential descent, D0 comparison)
            5. Binary search for MIN
            6. Store MIN, MAX, D per frame

        No normalization. No averaging. No multi-frame probes.
        Pure: STATE_t --(ACTION per frame)--> STATE_t+1
        """
        config = self.actions_config[action_name]

        disc = FrameBinDiscovery(action_name)
        result = ActionDiscoveryResult(action_name=action_name)
        t0 = time.time()

        def make_action(value: float) -> Dict[str, float]:
            """Build action dict with only test action non-zero."""
            a = {name: 0.0 for name in self.actions_config}
            a[action_name] = value  # No clamping — let the environment reject
            return a

        def probe_one_frame(value: float) -> ProbeResult:
            """Execute ONE probe: discovery's pure single-frame transition.

            Protocol (exactly discovery's experimentation_algorithm.md):
                1. Read state_before
                2. Apply action for exactly one frame
                3. Read state_after
                4. delta = state_after - state_before

            No normalization. No averaging. No multi-frame.
            Pure: STATE_t --(ACTION per frame)--> STATE_t+1

            For steering: needs a coast frame to establish heading baseline
            (no yaw in telemetry, heading computed from position deltas).
            """
            for attempt in range(self.MAX_PROBE_RETRIES):
                # For steering heading: need pre_before for displacement vector
                fb_pre = get_feedbacks_fn()
                if action_name == 'steering':
                    # Coast 1 frame to get heading baseline (action=0 is a real action)
                    send_action_fn({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
                    wait_fn(frame_duration_s)

                fb_before = get_feedbacks_fn()
                send_action_fn(make_action(value))
                wait_fn(frame_duration_s)  # Exactly one frame
                fb_after = get_feedbacks_fn()

                # Release action
                send_action_fn({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})

                delta = disc.compute_delta(
                    fb_before, fb_after,
                    action_name=action_name,
                    pre_before=fb_pre
                )

                if delta is not None:
                    break  # Valid probe
                if attempt < self.MAX_PROBE_RETRIES - 1:
                    logger.warning(f"    Probe invalid (low displacement), "
                                   f"retry {attempt+2}/{self.MAX_PROBE_RETRIES}")

            # Determine validity — NEVER inject fake delta
            is_valid = delta is not None
            if not is_valid:
                logger.warning(f"    Probe INVALID after {self.MAX_PROBE_RETRIES} attempts. "
                               f"Marking valid=False (not injecting fake data).")
                delta = 0.0  # Placeholder for dataclass, but valid=False excludes it

            # Set per-action epsilon on first probe
            if disc.measurement_epsilon is None:
                disc.measurement_epsilon = action_epsilon
                logger.info(f"  Epsilon: {disc.measurement_epsilon} "
                             f"(per-action, {action_name})")

            self.total_experiments += 1
            result.experiments_run += 1

            pr = ProbeResult(
                action_value=clamped,
                delta_state=delta,
                feedback_before=fb_before.copy(),
                feedback_after=fb_after.copy(),
                frame_duration_s=frame_duration_s,
                feedback_pre_before=fb_pre.copy(),
                valid=is_valid
            )
            disc.probes.append(pr)
            result.probe_log.append({
                'step': self.total_experiments,
                'action': clamped,
                'delta': delta,
                'valid': is_valid,
                'speed_before': fb_before.get('speed', 0),
                'speed_after': fb_after.get('speed', 0)
            })
            return pr

        # =====================================================
        # RUN DISCOVERY (discovery's exact 6-step algorithm)
        # =====================================================
        logger.info(f"[DISCOVERY] {action_name}: Running discovery's exact algorithm")
        logger.info(f"  Range: {action_range}, Precision: {self.search_precision}")
        logger.info(f"  Epsilon: {action_epsilon} (no normalization — pure discovery)")
        logger.info(f"  Frame duration: {frame_duration_s*1000:.0f}ms (1 frame per probe)")

        self.phase = ExperimentationPhase.MEASURING_DELTA0
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
        logger.info(f"  Epsilon: {disc.measurement_epsilon}")

        # =====================================================
        # BUILD BINS: uniform divisions of [MIN, MAX]
        # =====================================================
        # discovery: "Store MIN, MAX, Δ per frame"
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
            'algorithm': 'discovery_algorithm',
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

    Runs discovery's exact algorithm for each action in sequence.
    """

    def __init__(
        self,
        actions_config: Dict[str, Any],
        send_action_fn: Callable[[Dict[str, float]], None],
        get_feedbacks_fn: Callable[[], Dict[str, float]],
        wait_fn: Callable[[float], None] = None,
        reset_fn: Callable[[], None] = None,
        reset_fns: Optional[Dict[str, Callable]] = None,
        frame_duration_s: float = 0.05
    ):
        self.intelligence = ExperimentationIntelligence(actions_config)
        self.send_action = send_action_fn
        self.get_feedbacks = get_feedbacks_fn
        self.wait = wait_fn or (lambda t: time.sleep(t))
        self.reset_fn = reset_fn
        self.reset_fns = reset_fns or {}
        self.frame_duration_s = frame_duration_s

    def run_full_experimentation(self) -> Dict[str, List[Dict[str, Any]]]:
        """Run discovery's exact algorithm for ALL actions."""
        logger.info("[COORDINATOR] Starting discovery's exact experimentation")
        logger.info(f"  Frame duration: {self.frame_duration_s*1000:.0f}ms "
                     f"(1 frame per probe, no temporal aggregation)")
        self.intelligence.start_time = time.time()

        for action_name in self.intelligence.actions_config:
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
