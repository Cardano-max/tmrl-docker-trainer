"""
INTELLIGENCE: Experimentation - Sutton-Correct Bin Discovery

CORE AXIOMS (non-negotiable):

A. FRAME IS LAW
   - Time is NOT continuous. Everything happens per frame.
   - Frame duration = CONFIG control step (e.g., 50ms = 20Hz).
     NOT the telemetry streaming rate (which may be ~500Hz).
     The "frame" is how long we HOLD an action before measuring effect.
   - Cannot invent smaller time slices.
   - Any action that takes longer than one frame spans multiple frames.
   - This is saturation + quantization, not feedback noise.
   - MULTI-FRAME PROBES: To get stable per-frame delta measurements,
     we hold the action for N frames and divide total delta by N.
     This averages out per-frame noise while preserving per-frame semantics.

B. ACTIONS ARE BOUNDED BY THE CONTROLLER, NOT BY FEEDBACK
   - Feedback is environment-dependent, noisy, nonlinear.
   - Action bounds (min/max) are properties of:
     * controller resolution
     * API input quantization
     * per-frame input acceptance
   - We discover action bounds VIA feedback, but do NOT define bins in feedback space.

C. BINS ARE ABOUT WHAT YOU CAN DO, NOT WHAT HAPPENS
   - You control action. You observe feedback.
   - Knowledge graph must discretize ACTION CAPABILITY, not outcome.
   - Bins = equivalence classes of actions that produce indistinguishable
     state transitions within one frame.
   - Formally: a1, a2 in same bin if |delta_state(a1) - delta_state(a2)| < epsilon

ALGORITHM (4 steps, Sutton-validated):

Step 0: Preconditions
  - Fixed FPS from environment
  - Fixed initial state s0
  - Single frame transition
  - Repeatable setup (reset to s0 each probe)

Step 1: Discover MAX effective action (upper saturation)
  - Send very large action (e.g., 10^6)
  - Measure delta_state -> delta_max
  - Decrease exponentially: 10^5, 10^4, ..., 1
  - Find smallest a where delta_state(a) ≈ delta_max
  - That a = max effective. Anything above = same bin (saturation bin)

Step 2: Discover MIN effective action (lower quantization / dead-zone)
  - Start from very small: 1e-6, 1e-5, 1e-4, ...
  - Apply for exactly one frame
  - Find smallest a where |delta_state| > noise_threshold
  - That a = minimum effective. Below = zero-effect bin (dead-zone)

Step 3: Discover intermediate bins (multiplicity test)
  - Let a_k = k * a_min for k = 1, 2, 3, ...
  - Apply each for one frame, record delta_state
  - Stop when delta_state saturates (≈ delta_max)
  - Group by delta_state similarity:
    If delta(a_k) ≈ delta(a_{k+1}) -> same bin, else -> new bin

Step 4: Precision discovery
  - From feedback decimals: precision = max decimal places observed
  - bin_resolution >= feedback_precision
  - Bins finer than feedback precision are meaningless
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
    MEASURING_BASELINE = "measuring_baseline"
    DISCOVERING_MAX = "discovering_max"
    DISCOVERING_MIN = "discovering_min"
    DISCOVERING_INTERMEDIATES = "discovering_intermediates"
    VALIDATING_BINS = "validating_bins"
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

    NOT about feedback ranges. About what you can DO.
    """
    bin_id: int
    a_min: float        # Minimum action value in this bin
    a_max: float        # Maximum action value in this bin
    label: str          # Human-readable label
    effect_mean: float  # Mean delta_state for actions in this bin

    def contains(self, value: float) -> bool:
        return self.a_min <= value < self.a_max

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bin_id': self.bin_id,
            'min': self.a_min,
            'max': self.a_max,
            'label': self.label,
            'effect_mean': self.effect_mean
        }


@dataclass
class ProbeResult:
    """Result of a single probe (one action, one frame)."""
    action_value: float
    delta_state: float  # |feedback_after - feedback_before| (max across feedbacks)
    feedback_before: Dict[str, float]
    feedback_after: Dict[str, float]
    frame_duration_s: float


@dataclass
class PrecisionResult:
    """System precision discovered from feedback decimal places."""
    feedback_name: str
    decimal_places: int
    min_observable_change: float
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feedback_name': self.feedback_name,
            'decimal_places': self.decimal_places,
            'min_observable_change': self.min_observable_change,
            'sample_count': self.sample_count
        }


@dataclass
class BaselineResult:
    """Baseline noise measurement: what happens with ZERO action."""
    n_samples: int
    mean_delta: float
    std_delta: float
    raw_deltas: List[float]
    noise_threshold: float  # mean + k * std (dynamic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_samples': self.n_samples,
            'mean_delta': self.mean_delta,
            'std_delta': self.std_delta,
            'noise_threshold': self.noise_threshold,
            'raw_deltas': self.raw_deltas
        }


@dataclass
class StateCondition:
    """An environment state used for bin validation."""
    label: str              # e.g., "low_speed", "high_speed", "turning"
    setup_description: str  # How to reach this state
    speed_range: Tuple[float, float] = (0.0, 999.0)


@dataclass
class BinValidationEntry:
    """Validation measurement for one bin at one state."""
    bin_id: int
    state_label: str
    action_tested: float    # Representative action from bin midpoint
    deltas: List[float]     # Multiple measurements at this state
    mean_delta: float
    std_delta: float


@dataclass
class BinValidationResult:
    """Result of Phase 5: state-robust bin validation."""
    n_states: int
    n_probes_per_bin_per_state: int
    entries: List[BinValidationEntry] = field(default_factory=list)
    merges: List[Tuple[int, int]] = field(default_factory=list)  # (bin_i, bin_j) merged
    splits: List[int] = field(default_factory=list)                # bin_ids that were split
    validated_bins: List['ActionBin'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_states': self.n_states,
            'n_probes_per_bin_per_state': self.n_probes_per_bin_per_state,
            'entries': [
                {
                    'bin_id': e.bin_id, 'state': e.state_label,
                    'action': e.action_tested,
                    'mean_delta': e.mean_delta, 'std_delta': e.std_delta,
                    'n_samples': len(e.deltas)
                }
                for e in self.entries
            ],
            'merges': self.merges,
            'splits': self.splits,
            'validated_bins': [b.to_dict() for b in self.validated_bins]
        }


@dataclass
class ActionDiscoveryResult:
    """Complete discovery result for one action."""
    action_name: str
    a_max_effective: float = 0.0
    a_min_effective: float = 0.0
    a_min_identifiable: bool = True   # False if min is contaminated by baseline
    is_binary: bool = False           # True if action is binary (only max value has effect)
    delta_max: float = 0.0            # Saturation delta
    system_precision: int = 6
    baseline: Optional[BaselineResult] = None
    validation: Optional[BinValidationResult] = None
    discovered_bins: List[ActionBin] = field(default_factory=list)
    probe_log: List[Dict[str, Any]] = field(default_factory=list)
    intermediate_deltas: List[Tuple[float, float]] = field(default_factory=list)
    experiments_run: int = 0
    discovery_time: float = 0.0
    discovery_source: DiscoverySource = DiscoverySource.EXPERIMENTATION
    success: bool = False
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_name': self.action_name,
            'a_max_effective': self.a_max_effective,
            'a_min_effective': self.a_min_effective,
            'a_min_identifiable': self.a_min_identifiable,
            'is_binary': self.is_binary,
            'delta_max': self.delta_max,
            'system_precision': self.system_precision,
            'baseline': self.baseline.to_dict() if self.baseline else None,
            'validation': self.validation.to_dict() if self.validation else None,
            'bins': [b.to_dict() for b in self.discovered_bins],
            'intermediate_deltas': [
                {'action': a, 'delta': d} for a, d in self.intermediate_deltas
            ],
            'experiments_run': self.experiments_run,
            'discovery_time': self.discovery_time,
            'discovery_source': self.discovery_source.value,
            'success': self.success,
            'probe_log': self.probe_log
        }


# =============================================================================
# SUTTON-CORRECT BIN DISCOVERY (per-action)
# =============================================================================

class FrameBinDiscovery:
    """
    Sutton-correct bin discovery for a single action.

    Bins = equivalence classes of actions that produce indistinguishable
    state transitions within one frame.

    Formally: a1, a2 in same bin iff delta_state(a1) ≈ delta_state(a2) within ε
    """

    # Tolerance for detecting when delta changes during max discovery.
    # Sutton: "if you go beyond the max the delta won't change"
    # "when the delta changes you have the max"
    DELTA_CHANGE_RATIO = 0.15  # Delta must drop >15% to count as "changed"

    # Tolerance for multiples proportionality check.
    # Sutton: "I would do a 0.3 to see if I move three times the 0.1... or very close to it"
    PROPORTIONALITY_TOLERANCE = 0.30  # 30% tolerance for k*min_delta check

    def __init__(
        self,
        action_name: str,
        action_range: Tuple[float, float],
        noise_threshold: float = 0.001
    ):
        self.action_name = action_name
        self.action_range = action_range
        self.noise_threshold = noise_threshold

        # Baseline noise measurement
        self.baseline: Optional[BaselineResult] = None

        # Results
        self.a_max_effective: Optional[float] = None
        self.a_min_effective: Optional[float] = None
        self.delta_max: float = 0.0
        self.delta_min: float = 0.0  # Delta at a_min_effective
        self.system_precision: int = 6

        # Probe history
        self.probes: List[ProbeResult] = []

        # Multiples results: (k, action_value, delta) triples
        self.multiples_map: List[Tuple[int, float, float]] = []

    # Feedback channels to use for delta computation (in priority order).
    # Noisy channels (distance, pos_x/y/z, rpm) change even when idle.
    # We prefer speed, then position, then fallback to max across all.
    # Primary keys for delta computation.
    # 'speed' is the reliable per-frame state channel for TrackMania.
    # 'position' is for environments like Pong that track position directly.
    # 'distance' is EXCLUDED: cumulative odometer, includes reset movement.
    # Verified: rpm fluctuates 3-25 at idle, input_* are our commands (ENVIRONMENT_VERIFICATION.md).
    PRIMARY_FEEDBACK_KEYS = ('speed', 'position')

    # Keys to EXCLUDE from fallback delta computation (noisy or non-state).
    EXCLUDED_FEEDBACK_KEYS = ('rpm', 'input_gas', 'input_brake', 'input_steer',
                               'gear', 'finished', 'distance',
                               'pos_x', 'pos_y', 'pos_z')

    def compute_delta(self, before: Dict[str, float], after: Dict[str, float], action_name: str = None) -> float:
        """Absolute feedback change using action-appropriate feedback channels.

        For steering: Uses position delta (heading change)
        For gas/brake: Uses speed delta

        Args:
            before: Feedback before action
            after: Feedback after action
            action_name: Which action was tested (gas/brake/steering)

        Returns:
            Delta in the appropriate feedback channel
        """
        # Special case: steering measures heading change from position
        if action_name == 'steering':
            if all(k in before and k in after for k in ('pos_x', 'pos_z')):
                import math
                x_before, z_before = before['pos_x'], before['pos_z']
                x_after, z_after = after['pos_x'], after['pos_z']

                # Compute heading change in degrees
                heading_before = math.atan2(z_before, x_before)
                heading_after = math.atan2(z_after, x_after)
                heading_delta = abs(heading_after - heading_before)

                # Also compute position distance as backup
                pos_delta = ((x_after - x_before)**2 + (z_after - z_before)**2)**0.5

                # Use max of heading change and position distance
                return max(heading_delta, pos_delta * 0.01)  # Scale position to match heading units

        # Default: gas/brake use speed
        if 'speed' in before and 'speed' in after:
            return abs(after['speed'] - before['speed'])

        # Fallback: use max delta across all valid channels
        max_delta = 0.0
        for k in before:
            if k in after and k not in self.EXCLUDED_FEEDBACK_KEYS:
                max_delta = max(max_delta, abs(after[k] - before[k]))
        return max_delta

    def effective_delta(self, raw_delta: float) -> float:
        """Subtract baseline noise from raw delta."""
        if self.baseline is None:
            return raw_delta
        return max(0.0, raw_delta - self.baseline.mean_delta)

    def update_precision(self, feedbacks: Dict[str, float]):
        """Track system precision from feedback decimal places.
        Sutton: "the feedback that the system gives you is the precision of the system"
        """
        for name, value in feedbacks.items():
            s = f"{value:.10f}".rstrip('0')
            if '.' in s:
                dec = len(s.split('.')[1])
                self.system_precision = max(self.system_precision, dec)

    # -----------------------------------------------------------------
    # SINGLE DESCENDING PASS: Discovers both MAX and MIN
    # -----------------------------------------------------------------
    # Sutton (Pong example):
    #   Send 100 -> delta=1 (saturated)
    #   Send 10  -> delta=1 (still saturated)
    #   Send 1   -> delta=1 (still saturated, this IS max)
    #   Send 0.1 -> delta=0.1 (delta CHANGED -> max is between 0.1 and 1)
    #   Send 0.01 -> delta=0 (no movement -> min is 0.1)
    # "the same algorithm you found the max and the min"

    def get_descending_test_sequence(self) -> List[float]:
        """Single descending sequence for finding max and min.

        Includes intermediate values (0.8, 0.5, 0.2) between 1.0 and 0.1
        so we can detect binary actions (where only max produces effect).

        Sutton: "the same algorithm you found the max and the min"
        """
        # High values (all clamp to range max): 10^6 down to 10
        seq = [10.0 ** exp for exp in range(6, 0, -1)]
        # Key range: 1.0, 0.8, 0.5, 0.2, 0.1 (reveals analog vs binary)
        seq.extend([1.0, 0.8, 0.5, 0.2, 0.1])
        # Low values: 0.01 down to 10^-6
        seq.extend([10.0 ** exp for exp in range(-2, -7, -1)])
        return seq

    def analyze_single_pass(
        self, probes: List[ProbeResult]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Analyze a single descending probe sequence.

        Returns (a_max_effective, a_min_effective).

        MAX detection (REQ-C02):
            "if you go beyond the max the delta won't change"
            "when the delta changes you have the max"
            Walk descending. While delta stays constant = above max.
            First probe where delta DROPS = max is between this and previous.

        MIN detection (REQ-C03):
            "the minimum you find when there's no movement"
            Continue descending past max.
            First probe where delta = 0 = below min.
            Min = the previous value (last with movement).
        """
        if not probes:
            return None, None

        # Phase 1: Find plateau delta (the first probe's delta is at saturation)
        self.delta_max = probes[0].delta_state

        if self.delta_max <= self.noise_threshold:
            return None, None

        # Phase 2: Walk down looking for delta drop (= found max)
        a_max = None
        prev_probe = probes[0]
        last_with_movement = probes[0]

        for i in range(1, len(probes)):
            probe = probes[i]

            # Check if delta dropped significantly from plateau
            if a_max is None and self.delta_max > 0:
                ratio = probe.delta_state / self.delta_max
                if ratio < (1.0 - self.DELTA_CHANGE_RATIO):
                    # Delta changed! Max is between prev and current.
                    # Sutton: "when the delta changes you have the max"
                    a_max = prev_probe.action_value
                    self.a_max_effective = a_max
                    logger.info(
                        f"  >>> MAX FOUND: delta dropped at a={probe.action_value:.6f} "
                        f"(delta={probe.delta_state:.6f} vs plateau={self.delta_max:.6f}). "
                        f"Max = {a_max:.6f} (previous probe)"
                    )

            # Track last probe with any movement (for min detection)
            if probe.delta_state > self.noise_threshold:
                last_with_movement = probe
            else:
                # Delta is zero = below min
                # Sutton: "the minimum you find when there's no movement"
                if self.a_min_effective is None:
                    self.a_min_effective = last_with_movement.action_value
                    self.delta_min = last_with_movement.delta_state
                    logger.info(
                        f"  >>> MIN FOUND: no movement at a={probe.action_value:.6f}. "
                        f"Min = {self.a_min_effective:.6f} (last with movement)"
                    )
                    break

            prev_probe = probe

        # If max not found (never dropped), use largest value
        if a_max is None:
            a_max = probes[0].action_value
            self.a_max_effective = a_max

        # If min not found (never reached zero), last with movement is best guess
        a_min = self.a_min_effective
        if a_min is None:
            a_min = last_with_movement.action_value
            self.a_min_effective = a_min
            self.delta_min = last_with_movement.delta_state

        return a_max, a_min

    # -----------------------------------------------------------------
    # MULTIPLES: Bins = k * min (REQ-B06)
    # -----------------------------------------------------------------

    def get_multiples_sequence(self) -> List[Tuple[int, float]]:
        """Generate (k, action_value) pairs: k*min for k=1,2,...,N where k*min <= max.

        Sutton: "the minimum ten times going to six and you have a register
        of one max going to six... the bins"
        """
        if not self.a_min_effective or not self.a_max_effective:
            return []

        result = []
        k = 1
        while True:
            a_k = k * self.a_min_effective
            if a_k > self.a_max_effective * 1.05:  # Small overshoot allowed
                break
            result.append((k, a_k))
            k += 1
            if k > 200:
                break
        return result

    def verify_proportionality(
        self, multiples_data: List[Tuple[int, float, float]]
    ) -> List[Dict[str, Any]]:
        """Verify that delta(k*min) ~= k * delta(min).

        Sutton: "I would do a 0.3 to see if I move three times the 0.1...
        or very close to it"

        Returns list of {k, action, delta, expected, ratio, pass} dicts.
        """
        self.multiples_map = multiples_data

        if not multiples_data or self.delta_min <= 0:
            return []

        results = []
        for k, action, delta in multiples_data:
            expected = k * self.delta_min
            ratio = delta / expected if expected > 0 else 0
            passed = abs(ratio - 1.0) <= self.PROPORTIONALITY_TOLERANCE
            results.append({
                'k': k, 'action': action, 'delta': delta,
                'expected': expected, 'ratio': ratio, 'pass': passed
            })

        return results

    def build_bins_from_multiples(
        self, multiples_data: List[Tuple[int, float, float]]
    ) -> List[ActionBin]:
        """Build bins as literal k*min values.

        Sutton: "when you have these multiples you have everything
        that the system needs"

        Each bin is one multiple: bin_k covers [k*min, (k+1)*min).
        Bin 0 = dead zone [0, min).
        """
        if not multiples_data:
            return self._fallback_bins()

        a_min = self.a_min_effective or 0.1
        a_max = self.a_max_effective or self.action_range[1]

        bins: List[ActionBin] = []

        # Bin 0: Dead-zone [0, min)
        bins.append(ActionBin(
            bin_id=0, a_min=0.0, a_max=a_min,
            label='DEAD_ZONE', effect_mean=0.0
        ))

        # Each multiple k*min is a bin: [k*min, (k+1)*min)
        n_multiples = len(multiples_data)
        labels = self._generate_labels(n_multiples + 1)

        for i, (k, action, delta) in enumerate(multiples_data):
            if i + 1 < n_multiples:
                next_action = multiples_data[i + 1][1]
            else:
                next_action = a_max + a_min  # Last bin extends past max

            bins.append(ActionBin(
                bin_id=k,
                a_min=action,
                a_max=next_action,
                label=labels[i + 1] if i + 1 < len(labels) else f'BIN_{k}',
                effect_mean=delta
            ))

        return bins

    def _fallback_bins(self) -> List[ActionBin]:
        """Fallback: create bins from just min/max if multiples unavailable.
        Uses k*min spacing."""
        a_min = self.a_min_effective or 0.1
        a_max = self.a_max_effective or self.action_range[1]

        # How many multiples fit?
        n_bins = max(1, int(a_max / a_min)) if a_min > 0 else 3
        n_bins = min(n_bins, 20)  # Cap at 20 bins

        labels = self._generate_labels(n_bins + 1)
        bins = [ActionBin(
            bin_id=0, a_min=0.0, a_max=a_min,
            label='DEAD_ZONE', effect_mean=0.0
        )]

        for k in range(1, n_bins + 1):
            b_min = k * a_min
            b_max = (k + 1) * a_min
            if k == n_bins:
                b_max = a_max + a_min
            bins.append(ActionBin(
                bin_id=k, a_min=b_min, a_max=b_max,
                label=labels[k] if k < len(labels) else f'BIN_{k}',
                effect_mean=0.0
            ))

        return bins

    def _generate_labels(self, n: int) -> List[str]:
        """Generate bin labels."""
        if n <= 2:
            return ['DEAD_ZONE', 'ACTIVE']
        elif n == 3:
            return ['DEAD_ZONE', 'LOW', 'HIGH']
        elif n == 4:
            return ['DEAD_ZONE', 'LOW', 'MED', 'HIGH']
        elif n == 5:
            return ['DEAD_ZONE', 'LOW', 'MED_LOW', 'MED_HIGH', 'HIGH']
        else:
            return ['DEAD_ZONE'] + [f'BIN_{i}' for i in range(1, n)]

    # -----------------------------------------------------------------
    # REQ-F02/B05: Clamp action to max per frame
    # -----------------------------------------------------------------

    def clamp_action(self, value: float) -> float:
        """Clamp action to [min_effective, max_effective] per frame.

        REQ-F02: "the max per frame is still the same... even if you want
        in one frame you cannot"
        REQ-B05: Values above max have no additional effect in one frame.
        """
        a_max = self.a_max_effective or self.action_range[1]
        return max(self.action_range[0], min(value, a_max))

    # -----------------------------------------------------------------
    # Bidirectional (steering) support
    # -----------------------------------------------------------------

    def make_bidirectional_bins(self, positive_bins: List[ActionBin]) -> List[ActionBin]:
        """Mirror bins for bidirectional action (e.g., steering -1 to +1)."""
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
                effect_mean=-b.effect_mean
            ))

        # Dead-zone centered at 0
        dz = positive_bins[0].a_max if positive_bins else 0.1
        result.append(ActionBin(
            bin_id=0,
            a_min=-dz,
            a_max=dz,
            label='STRAIGHT',
            effect_mean=0.0
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
                effect_mean=b.effect_mean
            ))

        return result


# =============================================================================
# EXPERIMENTATION INTELLIGENCE (orchestrates per-action discoveries)
# =============================================================================

class ExperimentationIntelligence:
    """
    Orchestrates bin discovery for all actions.

    TWO PATHS:
    1. DOCUMENTATION: Known system -> load min/max/bins directly
    2. EXPERIMENTATION: Unknown system -> run 4-step algorithm
    """

    def __init__(
        self,
        actions_config: Dict[str, Any],
        min_step: float = 0.01,
        max_iterations: int = 100,
        change_threshold: float = 0.001
    ):
        self.actions_config = actions_config
        self.noise_threshold = change_threshold

        self.phase = ExperimentationPhase.NOT_STARTED
        self.discovery_results: Dict[str, ActionDiscoveryResult] = {}
        self.discovered_bins: Dict[str, List[ActionBin]] = {}
        self.precision_results: Dict[str, PrecisionResult] = {}

        self.total_experiments = 0
        self.start_time = None
        self.end_time = None

        logger.info("[EXPERIMENTATION] Initialized (Sutton-correct 4-step algorithm)")
        logger.info(f"  noise_threshold={change_threshold}")
        logger.info(f"  Actions to discover: {list(actions_config.keys())}")

    # -----------------------------------------------------------------
    # PATH 1: Documentation-based
    # -----------------------------------------------------------------

    def load_from_documentation(
        self,
        documented_values: Dict[str, Dict[str, float]]
    ) -> Dict[str, List[ActionBin]]:
        """
        Load bins from system documentation.

        "If the system has documentation we don't need experimentation."
        """
        logger.info("[EXPERIMENTATION] Loading from DOCUMENTATION (known system)")

        for action_name, values in documented_values.items():
            if action_name not in self.actions_config:
                continue

            config = self.actions_config[action_name]
            is_bidir = config['range'][0] < 0
            a_min = values['min']
            a_max = values['max']

            disc = FrameBinDiscovery(action_name, tuple(config['range']), self.noise_threshold)
            disc.a_min_effective = a_min
            disc.a_max_effective = a_max
            disc.delta_max = a_max  # Approximation

            bins = disc._fallback_bins()
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

    def verify_documentation_multiples(
        self,
        action_name: str,
        send_action_fn: Callable,
        get_feedbacks_fn: Callable,
        wait_fn: Callable,
        reset_fn: Optional[Callable],
        frame_duration_s: float = 0.05,
        settle_frames: int = 6,
    ) -> List[Dict[str, Any]]:
        """REQ-E03: Even with documentation, verify that multiples work.

        "even if we know we might be able to test multiples for example...
        we need to know if the multiples work"
        """
        result = self.discovery_results.get(action_name)
        if not result:
            return []

        disc = FrameBinDiscovery(
            action_name, tuple(self.actions_config[action_name]['range']),
            self.noise_threshold
        )
        disc.a_min_effective = result.a_min_effective
        disc.a_max_effective = result.a_max_effective

        settle_time = settle_frames * frame_duration_s
        multiples_seq = disc.get_multiples_sequence()
        if len(multiples_seq) > 10:
            multiples_seq = multiples_seq[:10]

        multiples_data = []
        for k, a_k in multiples_seq:
            if reset_fn:
                reset_fn()
                wait_fn(settle_time)

            fb_before = get_feedbacks_fn()
            send_action_fn({action_name: a_k})
            wait_fn(frame_duration_s)
            fb_after = get_feedbacks_fn()
            send_action_fn({action_name: 0.0})

            delta = disc.compute_delta(fb_before, fb_after, action_name=action_name)
            multiples_data.append((k, a_k, delta))

        disc.delta_min = multiples_data[0][2] if multiples_data else 0
        return disc.verify_proportionality(multiples_data)

    # -----------------------------------------------------------------
    # PATH 2: Experimentation (called by coordinator)
    # -----------------------------------------------------------------

    def run_discovery_for_action(
        self,
        action_name: str,
        send_action_fn: Callable,
        get_feedbacks_fn: Callable,
        wait_fn: Callable,
        reset_fn: Optional[Callable] = None,
        frame_duration_s: float = 0.05,
        settle_frames: int = 6
    ) -> ActionDiscoveryResult:
        """
        Sutton-correct discovery for one action.

        SINGLE DESCENDING PASS finds both max and min (REQ-C04).
        Then multiples test verifies bins = k*min (REQ-B06, REQ-C06).
        All times in frame multiples (REQ-A03).

        Sutton (Pong): "the same algorithm you found the max and the min"

        Args:
            settle_frames: Number of frames to wait after reset (replaces
                arbitrary 0.3s sleep). REQ-A03 compliance.
        """
        config = self.actions_config[action_name]
        action_range = (config['range'][0], config['range'][1])
        is_bidir = config['range'][0] < 0

        disc = FrameBinDiscovery(action_name, action_range, self.noise_threshold)
        result = ActionDiscoveryResult(action_name=action_name)
        t0 = time.time()

        # REQ-A03: settle time in frame multiples, not arbitrary seconds
        settle_time = settle_frames * frame_duration_s

        def make_action(value: float) -> Dict[str, float]:
            """Build action dict with only test action non-zero."""
            a = {name: 0.0 for name in self.actions_config}
            a[action_name] = max(action_range[0], min(value, action_range[1]))
            return a

        

        def probe_one_frame(value: float) -> ProbeResult:
            """Execute ONE probe: reset, send action for ONE frame, measure.
            Sutton: All probing is per-frame. REQ-A03: times in frame multiples.
            REQ-A02: Warns if processing exceeds frame_duration.
            """
            if reset_fn:
                reset_fn()
                wait_fn(settle_time)

            cycle_start = time.time()
            fb_before = get_feedbacks_fn()
            clamped = max(action_range[0], min(value, action_range[1]))
            send_action_fn(make_action(clamped))
            wait_fn(frame_duration_s)  # Exactly one frame
            fb_after = get_feedbacks_fn()
            cycle_time = time.time() - cycle_start
            if cycle_time > frame_duration_s * 2:
                logger.warning(
                    f"  [FRAME-MISS] Cycle took {cycle_time*1000:.1f}ms "
                    f"(frame={frame_duration_s*1000:.1f}ms)"
                )

            # Release
            send_action_fn({k: 0.0 for k in self.actions_config})

            delta = disc.compute_delta(fb_before, fb_after, action_name=action_name)
            disc.update_precision(fb_after)
            self.total_experiments += 1
            result.experiments_run += 1

            pr = ProbeResult(
                action_value=clamped,
                delta_state=delta,
                feedback_before=fb_before.copy(),
                feedback_after=fb_after.copy(),
                frame_duration_s=frame_duration_s
            )
            disc.probes.append(pr)
            result.probe_log.append({
                'step': self.total_experiments,
                'action': clamped,
                'delta': delta,
                'phase': 'discovery',
                'speed_before': fb_before.get('speed', 0),
                'speed_after': fb_after.get('speed', 0)
            })
            return pr

        # =====================================================
        # STEP 0: BASELINE (mandatory)
        # =====================================================
        BASELINE_N = 15
        BASELINE_K = 3.0

        logger.info(f"[STEP 0] {action_name}: Measuring baseline ({BASELINE_N} frames)...")
        self.phase = ExperimentationPhase.MEASURING_BASELINE

        baseline_deltas = []
        for i in range(BASELINE_N):
            if reset_fn:
                reset_fn()
                wait_fn(settle_time)

            fb_before = get_feedbacks_fn()
            send_action_fn({k: 0.0 for k in self.actions_config})
            wait_fn(frame_duration_s)
            fb_after = get_feedbacks_fn()

            delta = disc.compute_delta(fb_before, fb_after)
            baseline_deltas.append(delta)
            disc.update_precision(fb_after)
            self.total_experiments += 1
            result.experiments_run += 1

            result.probe_log.append({
                'step': self.total_experiments, 'action': 0.0,
                'delta': delta, 'phase': 'baseline',
                'speed_before': fb_before.get('speed', 0),
                'speed_after': fb_after.get('speed', 0)
            })

        bl_mean = sum(baseline_deltas) / len(baseline_deltas) if baseline_deltas else 0.0
        bl_var = sum((d - bl_mean) ** 2 for d in baseline_deltas) / max(1, len(baseline_deltas) - 1)
        bl_std = bl_var ** 0.5
        bl_threshold = bl_mean + BASELINE_K * bl_std

        disc.baseline = BaselineResult(
            n_samples=BASELINE_N, mean_delta=bl_mean,
            std_delta=bl_std, raw_deltas=baseline_deltas,
            noise_threshold=bl_threshold
        )
        result.baseline = disc.baseline
        # Enforce minimum noise floor — even with perfect baseline,
        # sub-0.001 deltas are meaningless for physical actions.
        # Verified: gas=1.0 delta ~0.16, baseline ~0.000008 (see ENVIRONMENT_VERIFICATION.md)
        bl_threshold = max(bl_threshold, self.noise_threshold)
        disc.noise_threshold = bl_threshold

        logger.info(f"  BASELINE: mean={bl_mean:.6f}, std={bl_std:.6f}, "
                     f"threshold={bl_threshold:.6f} (mean + {BASELINE_K}*std)")

        # =====================================================
        # STEP 1+2: SINGLE DESCENDING PASS (REQ-C04)
        # =====================================================
        # "the same algorithm you found the max and the min"
        # Descend: 10^6, 10^5, ..., 1, 0.1, 0.01, ...
        # MAX = when delta first DROPS from plateau (REQ-C02)
        # MIN = when delta becomes zero (REQ-C03)
        logger.info(f"[STEP 1+2] {action_name}: Single descending pass (max + min)...")
        self.phase = ExperimentationPhase.DISCOVERING_MAX

        descending_probes = []
        for test_val in disc.get_descending_test_sequence():
            pr = probe_one_frame(test_val)
            eff = disc.effective_delta(pr.delta_state)
            # Store effective delta for analysis
            pr.delta_state = eff
            descending_probes.append(pr)

            logger.info(
                f"  PROBE: a={pr.action_value:.6f} -> "
                f"raw={disc.compute_delta(pr.feedback_before, pr.feedback_after, action_name=action_name):.6f}, "
                f"effective={eff:.6f}"
            )

        a_max, a_min = disc.analyze_single_pass(descending_probes)

        if a_max is None:
            a_max = action_range[1]
            logger.warning(f"  MAX not found, using range max: {a_max}")
        if a_min is None:
            a_min = action_range[1] * 0.01
            result.a_min_identifiable = False
            logger.warning(
                f"  MIN not identifiable (baseline_mean={bl_mean:.6f}, "
                f"threshold={bl_threshold:.6f}). Fallback: {a_min}"
            )
        else:
            result.a_min_identifiable = True

        result.a_max_effective = a_max
        result.a_min_effective = a_min
        result.delta_max = disc.delta_max

        logger.info(f"  >>> MAX = {a_max}, MIN = {a_min}, "
                     f"delta_max = {disc.delta_max:.6f}, "
                     f"identifiable = {result.a_min_identifiable}")

        # =====================================================
        # STEP 2.5: BINARY ACTION DETECTION
        # =====================================================
        # Verified truth: TrackMania treats gas/brake as binary.
        # The game ignores analog values below ~1.0.
        # Detection: if only the clamped-max probes produce effect
        # and ALL sub-max probes produce zero, the action is binary.
        #
        # We confirm by probing a few intermediate values (0.5, 0.2)
        # to verify they produce zero effect.

        is_binary = False
        if disc.delta_max > disc.noise_threshold:
            # Check: did any sub-max probes produce effect?
            clamped_max = min(action_range[1], max(p.action_value for p in descending_probes))
            sub_max_probes = [p for p in descending_probes
                              if p.action_value < clamped_max * 0.99]
            sub_max_with_effect = [p for p in sub_max_probes
                                   if p.delta_state > disc.noise_threshold]

            if len(sub_max_with_effect) == 0 and len(sub_max_probes) > 0:
                # All sub-max probes had zero effect. Confirm with targeted probes.
                logger.info(f"  [BINARY CHECK] No sub-max probes had effect. Confirming...")
                confirm_values = [action_range[1] * v for v in [0.5, 0.2, 0.8]]
                confirm_zeros = 0
                for cv in confirm_values:
                    pr = probe_one_frame(cv)
                    eff = disc.effective_delta(pr.delta_state)
                    # Also check input readback if available
                    input_key = f'input_{action_name}'
                    input_readback = pr.feedback_after.get(input_key, None)
                    logger.info(
                        f"  [BINARY CHECK] a={cv:.2f} -> delta={eff:.6f}"
                        f"{f', TM_input={input_readback}' if input_readback is not None else ''}"
                    )
                    if eff <= disc.noise_threshold:
                        confirm_zeros += 1

                if confirm_zeros >= 2:  # At least 2 of 3 confirm zero
                    is_binary = True
                    a_max = action_range[1]
                    a_min = action_range[1]  # For binary: min = max
                    disc.a_max_effective = a_max
                    disc.a_min_effective = a_min
                    result.a_max_effective = a_max
                    result.a_min_effective = a_min
                    result.is_binary = True
                    logger.info(
                        f"  >>> BINARY ACTION DETECTED: only a={a_max} produces effect. "
                        f"All intermediate values ignored by environment."
                    )

        if is_binary:
            # =====================================================
            # BINARY PATH: 2 bins only (DEAD_ZONE + FULL)
            # =====================================================
            logger.info(f"[STEP 3] {action_name}: SKIPPED (binary action, no gradient)")

            result.system_precision = disc.system_precision
            logger.info(f"[STEP 4] {action_name}: Precision = {disc.system_precision} decimals")

            bins = [
                ActionBin(
                    bin_id=0,
                    a_min=0.0,
                    a_max=action_range[1],
                    label='DEAD_ZONE',
                    effect_mean=0.0
                ),
                ActionBin(
                    bin_id=1,
                    a_min=action_range[1],
                    a_max=action_range[1],
                    label='FULL',
                    effect_mean=disc.delta_max
                ),
            ]

            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

        else:
            # =====================================================
            # ANALOG PATH: MULTIPLES TEST (REQ-B06, REQ-C06)
            # =====================================================
            # Bins = k * min for k = 1, 2, 3, ...
            # Sutton: "I would do a 0.3 to see if I move three times the 0.1"
            logger.info(f"[STEP 3] {action_name}: Multiples test (k * min)...")
            self.phase = ExperimentationPhase.DISCOVERING_INTERMEDIATES

            multiples_seq = disc.get_multiples_sequence()

            # Limit to 30 probes max
            if len(multiples_seq) > 30:
                step = len(multiples_seq) // 30
                multiples_seq = multiples_seq[::step]

            multiples_data = []  # (k, action, delta)
            for k, a_k in multiples_seq:
                pr = probe_one_frame(a_k)
                eff = disc.effective_delta(pr.delta_state)
                multiples_data.append((k, a_k, eff))

                result.probe_log.append({
                    'step': self.total_experiments, 'action': a_k,
                    'delta': eff, 'k': k, 'phase': 'multiples',
                    'speed_before': pr.feedback_before.get('speed', 0),
                    'speed_after': pr.feedback_after.get('speed', 0)
                })
                logger.info(f"  k={k}: a={a_k:.6f} -> delta={eff:.6f}")

            result.intermediate_deltas = [(a, d) for k, a, d in multiples_data]

            # Verify proportionality (REQ-C06)
            prop_results = disc.verify_proportionality(multiples_data)
            n_pass = sum(1 for r in prop_results if r['pass'])
            n_total = len(prop_results)
            if prop_results:
                logger.info(f"  PROPORTIONALITY: {n_pass}/{n_total} passed "
                           f"(tolerance={disc.PROPORTIONALITY_TOLERANCE*100:.0f}%)")
                for r in prop_results:
                    logger.info(f"    k={r['k']}: delta={r['delta']:.4f}, "
                               f"expected={r['expected']:.4f}, "
                               f"ratio={r['ratio']:.2f} "
                               f"{'PASS' if r['pass'] else 'FAIL'}")

            # =====================================================
            # STEP 4: Precision
            # =====================================================
            result.system_precision = disc.system_precision
            logger.info(f"[STEP 4] {action_name}: Precision = {disc.system_precision} decimals")

            # =====================================================
            # BUILD BINS from multiples (REQ-B06)
            # =====================================================
            if multiples_data:
                bins = disc.build_bins_from_multiples(multiples_data)
            else:
                bins = disc._fallback_bins()

            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

        result.discovered_bins = bins
        result.discovery_time = time.time() - t0
        result.success = True

        self.discovered_bins[action_name] = bins
        self.discovery_results[action_name] = result

        for pr in disc.probes:
            self._track_precision(pr.feedback_after)

        logger.info(f"  >>> {action_name}: {len(bins)} bins in {result.discovery_time:.1f}s")
        for b in bins:
            logger.info(f"    Bin {b.bin_id}: [{b.a_min:.4f}, {b.a_max:.4f}) = {b.label} (effect={b.effect_mean:.4f})")

        return result

    # -----------------------------------------------------------------
    # PHASE 5: State-robust bin validation
    # -----------------------------------------------------------------

    def validate_bins_for_action(
        self,
        action_name: str,
        send_action_fn: Callable,
        get_feedbacks_fn: Callable,
        wait_fn: Callable,
        state_setup_fns: List[Tuple[str, Callable]],
        frame_duration_s: float = 0.05,
        probes_per_bin_per_state: int = 3
    ) -> BinValidationResult:
        """
        PHASE 5: Validate discovered bins across multiple environment states.

        For each bin:
          For each state (e.g., low speed, high speed, turning):
            Apply representative action (bin midpoint) for one frame
            Measure delta_state

        Then:
          - If two adjacent bins have overlapping delta distributions -> MERGE
          - If one bin has bimodal delta distribution -> SPLIT (future)

        An action bin is valid iff it produces a distinguishable,
        state-robust transition class in one frame.
        """
        logger.info(f"[PHASE 5] {action_name}: Validating bins across {len(state_setup_fns)} states...")
        self.phase = ExperimentationPhase.VALIDATING_BINS

        result = self.discovery_results.get(action_name)
        if not result or not result.discovered_bins:
            logger.warning(f"  No bins to validate for {action_name}")
            return BinValidationResult(n_states=0, n_probes_per_bin_per_state=0)

        config = self.actions_config[action_name]
        action_range = (config['range'][0], config['range'][1])
        disc = FrameBinDiscovery(action_name, action_range)
        if result.baseline:
            disc.baseline = result.baseline

        candidate_bins = [b for b in result.discovered_bins if b.bin_id != 0]  # Skip dead-zone
        validation = BinValidationResult(
            n_states=len(state_setup_fns),
            n_probes_per_bin_per_state=probes_per_bin_per_state
        )

        def make_action(value: float) -> Dict[str, float]:
            a = {name: 0.0 for name in self.actions_config}
            a[action_name] = max(action_range[0], min(value, action_range[1]))
            return a

        # Collect deltas per bin across all states
        # bin_id -> {state_label -> [deltas]}
        bin_state_deltas: Dict[int, Dict[str, List[float]]] = {}

        for state_label, setup_fn in state_setup_fns:
            logger.info(f"  State: {state_label}")

            for b in candidate_bins:
                # Representative action = midpoint of bin
                rep_action = (b.a_min + b.a_max) / 2.0
                rep_action = max(action_range[0], min(rep_action, action_range[1]))

                deltas = []
                for _ in range(probes_per_bin_per_state):
                    setup_fn()
                    wait_fn(0.1)

                    fb_before = get_feedbacks_fn()
                    send_action_fn(make_action(rep_action))
                    wait_fn(frame_duration_s)
                    fb_after = get_feedbacks_fn()

                    # Release
                    send_action_fn({k: 0.0 for k in self.actions_config})

                    raw = disc.compute_delta(fb_before, fb_after, action_name=action_name)
                    eff = disc.effective_delta(raw)
                    deltas.append(eff)
                    self.total_experiments += 1

                mean_d = sum(deltas) / len(deltas) if deltas else 0.0
                var_d = sum((d - mean_d) ** 2 for d in deltas) / max(1, len(deltas) - 1) if len(deltas) > 1 else 0.0
                std_d = var_d ** 0.5

                entry = BinValidationEntry(
                    bin_id=b.bin_id,
                    state_label=state_label,
                    action_tested=rep_action,
                    deltas=deltas,
                    mean_delta=mean_d,
                    std_delta=std_d
                )
                validation.entries.append(entry)

                if b.bin_id not in bin_state_deltas:
                    bin_state_deltas[b.bin_id] = {}
                bin_state_deltas[b.bin_id][state_label] = deltas

                logger.info(f"    Bin {b.bin_id} ({b.label}): a={rep_action:.4f} "
                           f"-> mean={mean_d:.4f}, std={std_d:.4f}")

        # ----- MERGE DECISION -----
        # Two adjacent bins should be merged if their cross-state delta
        # distributions overlap (means within 1 std of each other)
        merged_ids = set()
        sorted_bins = sorted(candidate_bins, key=lambda b: b.bin_id)

        for i in range(len(sorted_bins) - 1):
            b1 = sorted_bins[i]
            b2 = sorted_bins[i + 1]

            if b1.bin_id in merged_ids or b2.bin_id in merged_ids:
                continue

            # Get all deltas across all states for each bin
            all_d1 = []
            all_d2 = []
            for state_deltas in bin_state_deltas.get(b1.bin_id, {}).values():
                all_d1.extend(state_deltas)
            for state_deltas in bin_state_deltas.get(b2.bin_id, {}).values():
                all_d2.extend(state_deltas)

            if not all_d1 or not all_d2:
                continue

            mean1 = sum(all_d1) / len(all_d1)
            mean2 = sum(all_d2) / len(all_d2)
            std1 = (sum((d - mean1) ** 2 for d in all_d1) / max(1, len(all_d1) - 1)) ** 0.5
            std2 = (sum((d - mean2) ** 2 for d in all_d2) / max(1, len(all_d2) - 1)) ** 0.5

            # Overlap test: means within combined std
            combined_std = max(std1, std2, 0.001)
            separation = abs(mean2 - mean1) / combined_std

            if separation < 1.5:
                # Distributions overlap -> merge
                logger.info(f"  MERGE: Bin {b1.bin_id} + Bin {b2.bin_id} "
                           f"(separation={separation:.2f} < 1.5)")
                validation.merges.append((b1.bin_id, b2.bin_id))
                merged_ids.add(b2.bin_id)

        # Build validated bins
        validated = [b for b in result.discovered_bins if b.bin_id == 0]  # Keep dead-zone

        for b in sorted_bins:
            if b.bin_id in merged_ids:
                # This bin was merged into the previous one - extend previous
                if validated:
                    validated[-1].a_max = b.a_max
                    # Update effect_mean as average
                    all_d = []
                    for state_deltas in bin_state_deltas.get(b.bin_id, {}).values():
                        all_d.extend(state_deltas)
                    prev_d = []
                    for state_deltas in bin_state_deltas.get(validated[-1].bin_id, {}).values():
                        prev_d.extend(state_deltas)
                    all_combined = prev_d + all_d
                    if all_combined:
                        validated[-1].effect_mean = sum(all_combined) / len(all_combined)
            else:
                # Update effect_mean with cross-state measurement
                all_d = []
                for state_deltas in bin_state_deltas.get(b.bin_id, {}).values():
                    all_d.extend(state_deltas)
                if all_d:
                    b.effect_mean = sum(all_d) / len(all_d)
                validated.append(b)

        # Renumber validated bins
        for i, b in enumerate(validated):
            b.bin_id = i

        validation.validated_bins = validated

        logger.info(f"  VALIDATION COMPLETE: {len(result.discovered_bins)} -> {len(validated)} bins")
        logger.info(f"    Merges: {len(validation.merges)}")
        for b in validated:
            logger.info(f"    Bin {b.bin_id}: [{b.a_min:.4f}, {b.a_max:.4f}) = {b.label} (effect={b.effect_mean:.4f})")

        # Update result
        result.validation = validation
        result.discovered_bins = validated
        self.discovered_bins[action_name] = validated

        return validation

    def _track_precision(self, feedbacks: Dict[str, float]):
        """Track feedback precision."""
        for name, value in feedbacks.items():
            s = f"{value:.10f}".rstrip('0')
            dec = len(s.split('.')[1]) if '.' in s else 0

            if name not in self.precision_results:
                self.precision_results[name] = PrecisionResult(
                    feedback_name=name,
                    decimal_places=dec,
                    min_observable_change=10 ** (-dec) if dec > 0 else 1.0,
                    sample_count=1
                )
            else:
                pr = self.precision_results[name]
                pr.sample_count += 1
                if dec > pr.decimal_places:
                    pr.decimal_places = dec
                    pr.min_observable_change = 10 ** (-dec)

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
                        f"max={r.a_max_effective if r else '?'}")
        if self.precision_results:
            logger.info("  Precision:")
            for n, p in self.precision_results.items():
                logger.info(f"    {n}: {p.decimal_places} decimals")
        logger.info("=" * 70)

    # -----------------------------------------------------------------
    # Public API (compatible with existing coordinator interface)
    # -----------------------------------------------------------------

    def get_discovered_bins(self) -> Dict[str, List[Dict[str, Any]]]:
        result = {}
        for name, bins in self.discovered_bins.items():
            result[name] = [b.to_dict() for b in bins]
        return result

    def get_precision_results(self) -> Dict[str, Dict[str, Any]]:
        return {n: p.to_dict() for n, p in self.precision_results.items()}

    def is_complete(self) -> bool:
        return self.phase == ExperimentationPhase.COMPLETED

    def is_failed(self) -> bool:
        return self.phase == ExperimentationPhase.FAILED

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'phase': self.phase.value,
            'algorithm': 'sutton_correct_4step',
            'total_experiments': self.total_experiments,
            'actions_discovered': len(self.discovered_bins),
            'actions_total': len(self.actions_config),
            'elapsed_time': (time.time() - self.start_time) if self.start_time else 0,
            'precision': {n: p.to_dict() for n, p in self.precision_results.items()},
            'results': {n: r.to_dict() for n, r in self.discovery_results.items()}
        }

    def skip_experimentation_with_defaults(
        self, emergency_no_environment: bool = False
    ) -> Dict[str, List[ActionBin]]:
        if not emergency_no_environment:
            raise RuntimeError(
                "[REQ-003 VIOLATION] Cannot skip experimentation without "
                "emergency_no_environment=True."
            )

        logger.error("[EXPERIMENTATION] EMERGENCY: Using fallback bins (violates REQ-003)")

        for action_name, config in self.actions_config.items():
            is_bidir = config['range'][0] < 0
            disc = FrameBinDiscovery(action_name, tuple(config['range']))
            disc.a_min_effective = 0.1
            disc.a_max_effective = config['range'][1]
            disc.delta_max = config['range'][1]

            bins = disc._fallback_bins()
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

    Runs the 4-step algorithm for each action in sequence.
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
        self.reset_fns = reset_fns or {}  # Per-action reset overrides
        self.frame_duration_s = frame_duration_s

    def run_full_experimentation(
        self,
        state_setup_fns: Optional[List[Tuple[str, Callable]]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Run 4-step algorithm for ALL actions, then validate if states provided.

        Args:
            state_setup_fns: Optional list of (label, setup_fn) tuples.
                Each setup_fn puts the environment into a specific state
                for bin validation (Phase 5). If None, validation is skipped.
        """
        logger.info("[COORDINATOR] Starting Sutton-correct experimentation")
        self.intelligence.start_time = time.time()

        for action_name in self.intelligence.actions_config:
            logger.info(f"\n{'='*60}")
            logger.info(f"  DISCOVERING: {action_name}")
            logger.info(f"{'='*60}")

            # Use per-action reset if available, else default
            action_reset = self.reset_fns.get(action_name, self.reset_fn)

            self.intelligence.run_discovery_for_action(
                action_name=action_name,
                send_action_fn=self.send_action,
                get_feedbacks_fn=self.get_feedbacks,
                wait_fn=self.wait,
                reset_fn=action_reset,
                frame_duration_s=self.frame_duration_s
            )

        # Phase 5: State-robust bin validation
        if state_setup_fns:
            for action_name in self.intelligence.actions_config:
                logger.info(f"\n{'='*60}")
                logger.info(f"  VALIDATING: {action_name}")
                logger.info(f"{'='*60}")

                self.intelligence.validate_bins_for_action(
                    action_name=action_name,
                    send_action_fn=self.send_action,
                    get_feedbacks_fn=self.get_feedbacks,
                    wait_fn=self.wait,
                    state_setup_fns=state_setup_fns,
                    frame_duration_s=self.frame_duration_s
                )

        self.intelligence._complete()
        return self.intelligence.get_discovered_bins()

    def run_from_documentation(
        self, documented_values: Dict[str, Dict[str, float]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        return self.intelligence.load_from_documentation(documented_values)
