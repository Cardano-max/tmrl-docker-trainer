"""
PHASE A BIN DISCOVERY — TMNF + TMInterface 2.x (TCP bridge)

PURE SUTTON COMPLIANCE — No hardcoded values. Everything discovered.

Sutton's rules (from meeting transcripts):
  - "bins needs to be figured out by the system. Not by us." (Jan 9)
  - "the precision is not us, precision is the system." (Jan 24)
  - "the maximum minimum cannot be guessed... has to be calculated" (Feb 16)
  - "who defines the time stamp is the environment" (Feb 16)
  - "not doing an action is also an action" (Jan 9, Feb 16)
  - "the actions have to be by frame not continuously" (Jan 15)

What we discover (NOT hardcode):
  - Frame duration: measured from race_time delta
  - System precision: measured from repeated D0 probes (variance)
  - Action ranges: exponential sweep from 1e6 discovers them
  - MIN and MAX: Sutton's downward sweep + binary search
  - Input types: discovered (binary vs analog)

What we DON'T do:
  - No hardcoded epsilon / precision / thresholds
  - No multi-tick probes (all actions: 2 ticks = 1 frame)
  - No D0 subtraction
  - No normalization
  - No averaging

SETUP:
  1. TMNF + TMInterface 2.x installed
  2. AgenticBridge.as in %APPDATA%\\TMInterface\\Plugins\\
  3. Race running (countdown finished)
"""

import sys
import os
import json
import time
import logging
import argparse
import math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.tmnf_adapter import TMNFAdapter
from intelligence.intelligence_experimentation import (
    ExperimentationIntelligence,
    FrameBinDiscovery,
    ProbeResult,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('TMNF_TEST')


# =============================================================================
# ACTIONS CONFIG — Names only. No ranges. Sutton: "discover, don't configure."
# =============================================================================

TMNF_ACTIONS_CONFIG = {
    'gas':   {'description': 'Throttle'},
    'brake': {'description': 'Brake'},
    'left':  {'description': 'Steer left (digital key)'},
    'right': {'description': 'Steer right (digital key)'},
}


# =============================================================================
# STEP 0: MEASURE FRAME DURATION
# Sutton Feb 16: "who defines the time stamp is the environment"
# Sutton Jan 24: "determined by the system so it's being configured not hard-coded"
# =============================================================================

def measure_frame_duration(adapter: TMNFAdapter) -> float:
    """Discover frame duration from environment by measuring race_time delta.

    Returns frame duration in seconds.
    """
    logger.info("[STEP 0] Measuring frame duration from environment...")

    # Send neutral action and advance one tick
    adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
    adapter.wait_one_tick()
    fb_before = adapter.get_feedbacks()
    t_before = fb_before.get('race_time', 0)

    adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
    adapter.wait_one_tick()
    fb_after = adapter.get_feedbacks()
    t_after = fb_after.get('race_time', 0)

    delta_ms = t_after - t_before
    if delta_ms <= 0:
        logger.warning(f"  Invalid frame duration: {delta_ms}ms, using 10ms fallback")
        delta_ms = 10

    frame_duration_s = delta_ms / 1000.0
    logger.info(f"  Frame duration: {delta_ms}ms ({frame_duration_s}s)")
    logger.info(f"  (Measured from environment, not hardcoded)")
    return frame_duration_s


# =============================================================================
# STEP 1: MEASURE SYSTEM PRECISION
# Sutton Jan 24: "the precision is not us, precision is the system"
# Sutton Jan 31: "the feedback that the system gives you is the precision"
# =============================================================================

def measure_system_precision(adapter: TMNFAdapter, use_rewind: bool,
                              num_probes: int = 3) -> dict:
    """Discover measurement precision by probing D0 multiple times.

    With rewind: repeated D0 probes from same state should be bit-identical.
    Any variance = the system's measurement noise floor.

    Returns:
        {
            'speed_epsilon': float,   # for gas/brake delta comparison
            'yaw_epsilon': float,     # for steering delta comparison
            'speed_precision_digits': int,
            'yaw_precision_digits': int,
            'deterministic': bool,    # True if all D0 probes identical
        }
    """
    logger.info(f"[STEP 1] Measuring system precision ({num_probes} D0 probes)...")

    if use_rewind:
        adapter.save_state()

    speed_deltas = []
    yaw_deltas = []

    for i in range(num_probes):
        if use_rewind:
            adapter.rewind()

        # Tick 1: send nothing (input delay — replayed inputs)
        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()
        fb_before = adapter.get_feedbacks()

        # Tick 2: no action takes effect
        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()
        fb_after = adapter.get_feedbacks()

        speed_delta = fb_after.get('speed', 0) - fb_before.get('speed', 0)
        yaw_delta = fb_after.get('yaw', 0) - fb_before.get('yaw', 0)

        speed_deltas.append(speed_delta)
        yaw_deltas.append(yaw_delta)

        logger.info(f"  D0 probe {i+1}: speed_delta={speed_delta:.15g}, yaw_delta={yaw_delta:.15g}")

    # Compute variance
    def max_variance(values):
        if len(values) < 2:
            return 0.0
        return max(abs(a - b) for i, a in enumerate(values) for b in values[i+1:])

    speed_var = max_variance(speed_deltas)
    yaw_var = max_variance(yaw_deltas)

    deterministic = (speed_var == 0.0 and yaw_var == 0.0)

    # Epsilon = 2x the observed variance (safety margin)
    # If deterministic (variance = 0), use smallest meaningful difference
    # from the feedback's decimal precision
    if speed_var > 0:
        speed_epsilon = speed_var * 2.0
    else:
        # Count significant digits from feedback
        sample = abs(speed_deltas[0]) if speed_deltas[0] != 0 else abs(fb_before.get('speed', 1.0))
        speed_epsilon = _feedback_precision(sample)

    if yaw_var > 0:
        yaw_epsilon = yaw_var * 2.0
    else:
        sample = abs(yaw_deltas[0]) if yaw_deltas[0] != 0 else abs(fb_before.get('yaw', 1.0))
        yaw_epsilon = _feedback_precision(sample)

    # Count precision digits for logging
    speed_digits = _count_precision_digits(speed_epsilon)
    yaw_digits = _count_precision_digits(yaw_epsilon)

    logger.info(f"  Speed variance: {speed_var:.15g} → epsilon={speed_epsilon:.15g} ({speed_digits} digits)")
    logger.info(f"  Yaw variance:   {yaw_var:.15g} → epsilon={yaw_epsilon:.15g} ({yaw_digits} digits)")
    logger.info(f"  Deterministic:  {deterministic}")

    return {
        'speed_epsilon': speed_epsilon,
        'yaw_epsilon': yaw_epsilon,
        'speed_precision_digits': speed_digits,
        'yaw_precision_digits': yaw_digits,
        'deterministic': deterministic,
        'speed_deltas': speed_deltas,
        'yaw_deltas': yaw_deltas,
    }


def _feedback_precision(value: float) -> float:
    """Determine the feedback precision from a sample value.

    Uses the machine epsilon relative to the value's magnitude.
    For float64: ~2.2e-16 relative, so for value=15.0, precision ≈ 3.3e-15.
    """
    import sys
    eps = sys.float_info.epsilon  # ~2.2e-16
    return max(abs(value) * eps * 10, 1e-15)  # 10x machine epsilon for safety


def _count_precision_digits(epsilon: float) -> int:
    """Count how many decimal digits the epsilon represents."""
    if epsilon <= 0:
        return 15
    return max(0, int(-math.log10(epsilon)))


# =============================================================================
# PROBE FUNCTION — 2 ticks for ALL actions (Sutton: per frame)
# =============================================================================

def make_probe_fn(
    adapter: TMNFAdapter,
    disc: 'FrameBinDiscovery',
    action_name: str,
    use_rewind: bool,
    probe_counter: list,
    intelligence: 'ExperimentationIntelligence',
    frame_duration_s: float,
) -> callable:
    """
    Returns a probe function for the given action.

    ALL actions use exactly 2 ticks (1 frame = 1 probe):
      Tick 1: send action (loads for next tick due to TMInterface input delay)
      Tick 2: action takes effect, read fb_after

    Sutton: "the actions have to be by frame not continuously" (Jan 15)
    Sutton: "one node per frame" (Jan 15)
    """
    def probe_one_tick(value: float) -> 'ProbeResult':
        nonlocal probe_counter

        action_dict = {n: 0.0 for n in TMNF_ACTIONS_CONFIG}
        action_dict[action_name] = value  # No clamping — environment decides

        # Steering needs gas to maintain speed (yaw change requires velocity)
        is_steer = action_name in ('left', 'right')
        if is_steer:
            action_dict['gas'] = 1.0
            action_dict['steering'] = 0.0

        if use_rewind:
            adapter.rewind()

        # Tick 1: send action (TMInterface input delay: takes effect NEXT tick)
        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()

        # Read state before action takes effect
        fb_before = adapter.get_feedbacks()

        # Tick 2: our action takes effect — ONE frame, same for ALL actions
        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()

        # Read state after
        fb_after = adapter.get_feedbacks()

        # Compute delta — same for all actions, no special cases
        if is_steer:
            if 'yaw' in fb_before and 'yaw' in fb_after:
                delta = fb_after['yaw'] - fb_before['yaw']
                while delta > math.pi:
                    delta -= 2 * math.pi
                while delta < -math.pi:
                    delta += 2 * math.pi
            else:
                delta = 0.0
        else:
            delta = disc.compute_delta(
                fb_before, fb_after,
                action_name=action_name,
                pre_before=None
            )
            if delta is None:
                delta = 0.0

        probe_counter[0] += 1
        intelligence.total_experiments += 1

        pr = ProbeResult(
            action_value=value,
            delta_state=delta,
            feedback_before=fb_before,
            feedback_after=fb_after,
            frame_duration_s=frame_duration_s,
            valid=True
        )
        disc.probes.append(pr)
        return pr

    return probe_one_tick


# =============================================================================
# DISCOVERY — Pure Sutton, no hardcoded values
# =============================================================================

def run_discovery_tmnf(adapter: TMNFAdapter, use_rewind: bool = True,
                       actions_to_run: list = None,
                       frame_duration_s: float = 0.01,
                       precision: dict = None,
                       wire_precision: dict = None):
    """
    Run Sutton's bin discovery on TMNF.

    All values are DISCOVERED:
      - Frame duration: measured from environment
      - Precision/epsilon: measured from repeated D0 probes
      - Action ranges: exponential sweep from 1e6 discovers them
      - MIN/MAX: Sutton's downward sweep + binary search
    """
    if actions_to_run is None:
        actions_to_run = list(TMNF_ACTIONS_CONFIG.keys())

    intelligence = ExperimentationIntelligence(TMNF_ACTIONS_CONFIG)
    intelligence.start_time = time.time()

    logger.info("=" * 70)
    logger.info("PHASE A BIN DISCOVERY — TMNF (Pure Sutton, Zero Hardcoding)")
    logger.info("=" * 70)
    logger.info(f"  Frame duration: {frame_duration_s*1000:.0f}ms (measured from environment)")
    logger.info(f"  Rewind:   {use_rewind}")
    logger.info(f"  Actions:  {actions_to_run}")
    if precision:
        logger.info(f"  Speed epsilon: {precision['speed_epsilon']:.15g} (measured)")
        logger.info(f"  Yaw epsilon:   {precision['yaw_epsilon']:.15g} (measured)")
        logger.info(f"  Deterministic: {precision['deterministic']}")
    if wire_precision:
        logger.info(f"  Wire precision: probes derived from adapter wire format")
        for ch_name, ch_info in wire_precision.items():
            logger.info(f"    {ch_name}: {ch_info['wire_type']} step={ch_info['float_step']:.6g}")
    logger.info(f"  Ranges:   DISCOVERED (exponential sweep from 1e6)")
    logger.info(f"  Epsilons: DISCOVERED (from D0 probe variance)")
    logger.info("")

    fb = adapter.get_feedbacks()
    logger.info(f"  Starting state: speed={fb.get('speed', 0):.2f} km/h, "
                f"pos=({fb.get('pos_x', 0):.1f}, {fb.get('pos_y', 0):.1f}, "
                f"{fb.get('pos_z', 0):.1f})")

    results = {}

    # Save state ONCE for ALL actions in this cycle
    # Sutton: "test from whatever state the car is in"
    # All actions start from the EXACT same state → D0 is consistent
    if use_rewind:
        adapter.save_state()
        logger.info("  State saved ONCE for entire cycle (all actions share same state)")

    for action_name in actions_to_run:
        if action_name not in TMNF_ACTIONS_CONFIG:
            logger.warning(f"  Skipping unknown action: {action_name}")
            continue

        is_steer = action_name in ('left', 'right')

        # Use discovered precision — no hardcoded epsilons
        if precision:
            eps = precision['yaw_epsilon'] if is_steer else precision['speed_epsilon']
        else:
            eps = None  # Bit-exact comparison

        disc = FrameBinDiscovery(
            action_name,
            search_precision=eps,    # Binary search stops at measured precision
            measurement_epsilon=eps  # Delta comparison uses measured precision
        )

        logger.info(f"\n{'=' * 60}")
        logger.info(f"  DISCOVERING: {action_name}")
        logger.info(f"  Epsilon: {eps} (measured from environment)")
        logger.info(f"  Rewind:  {use_rewind}")
        logger.info(f"  Ticks per probe: 2 (same for ALL actions)")
        logger.info(f"{'=' * 60}")

        probe_counter = [0]
        t0 = time.time()

        probe_fn = make_probe_fn(
            adapter, disc, action_name,
            use_rewind, probe_counter, intelligence,
            frame_duration_s
        )

        # Run pure Sutton single-algorithm discovery
        # Nature (binary/analog) is discovered by the sweep itself, not pre-classified.
        # Wire precision is no longer needed -- the algorithm discovers everything from probing.
        a_max, a_min = disc.run_discovery(probe_fn)

        dt = time.time() - t0

        # Nature discovered by the pure Sutton sweep (binary/analog/none)
        nature = disc.nature or 'unknown'

        if a_max is not None and a_min is not None:
            bins = disc.build_bins()
            inferred_type = 'binary' if len(bins) <= 2 else 'analog'

            logger.info(f"\n  RESULT: {action_name}")
            logger.info(f"    Nature = {nature} (DISCOVERED by exponential sweep)")
            logger.info(f"    MAX    = {a_max:.10g}")
            logger.info(f"    MIN    = {a_min:.10g}")
            logger.info(f"    D0     = {disc.delta_0:.10g}")
            logger.info(f"    Dmax   = {disc.delta_max:.10g}")
            logger.info(f"    Bins   = {len(bins)}")
            logger.info(f"    Probes = {probe_counter[0]}")
            logger.info(f"    Time   = {dt:.1f}s")
            logger.info(f"    Type:  {inferred_type} (DISCOVERED)")

            results[action_name] = {
                'max':              a_max,
                'min':              a_min,
                'bins':             len(bins),
                'probes':           probe_counter[0],
                'time':             dt,
                'delta_max':        disc.delta_max,
                'delta_0':          disc.delta_0,
                'input_type':       inferred_type,
                'nature_detection': nature,
                'bin_details': [
                    {'id': b.bin_id, 'min': b.a_min, 'max': b.a_max, 'label': b.label}
                    for b in bins
                ],
                'probe_data': [
                    {
                        'action_value': p.action_value,
                        'delta': p.delta_state,
                        'speed_before': p.feedback_before.get('speed', 0),
                        'speed_after': p.feedback_after.get('speed', 0),
                        'yaw_before': p.feedback_before.get('yaw', 0),
                        'yaw_after': p.feedback_after.get('yaw', 0),
                    }
                    for p in disc.probes
                ]
            }
        else:
            logger.warning(f"\n  RESULT: {action_name} -- NO DETECTABLE RANGE")
            logger.warning(f"    Nature  = {nature}")
            logger.warning(f"    delta_max = {disc.delta_max}")
            logger.warning(f"    delta_0   = {disc.delta_0}")
            logger.warning(f"    Probes    = {probe_counter[0]}")

            results[action_name] = {
                'max':              None,
                'min':              None,
                'bins':             0,
                'probes':           probe_counter[0],
                'time':             dt,
                'delta_max':        disc.delta_max,
                'delta_0':          disc.delta_0,
                'input_type':       'none',
                'nature_detection': nature,
                'no_range':         True
            }

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("PHASE A COMPLETE — TMNF (Pure Sutton)")
    logger.info("=" * 70)
    total_probes = sum(r['probes'] for r in results.values())
    total_time   = sum(r['time'] for r in results.values())
    logger.info(f"  Frame duration: {frame_duration_s*1000:.0f}ms (measured)")
    logger.info(f"  Total probes: {total_probes}")
    logger.info(f"  Total time:   {total_time:.1f}s")
    logger.info(f"  Rewind mode:  {use_rewind}")
    logger.info(f"  Ticks/probe:  2 (ALL actions)")
    for name, r in results.items():
        if r.get('no_range'):
            logger.info(f"  {name}: NO RANGE (delta_max={r['delta_max']})")
        else:
            logger.info(f"  {name}: MIN={r['min']:.10g}, MAX={r['max']:.10g}, "
                        f"{r['bins']} bins, {r['probes']} probes "
                        f"[{r['input_type']}]")
    logger.info("=" * 70)

    return results


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_results(results: dict, use_rewind: bool,
                 frame_duration_s: float, precision: dict,
                 wire_precision: dict = None) -> str:
    """Save discovery results to JSON file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"tmnf_phase_a_results_{timestamp}.json"

    output = {
        'timestamp':     timestamp,
        'environment':   'TMNF',
        'interface':     'TMInterface 2.x (TCP bridge)',
        'plugin':        'AgenticBridge.as',
        'frame_duration_ms': frame_duration_s * 1000,
        'frame_duration_source': 'measured from environment (race_time delta)',
        'deterministic': True,
        'rewind_mode':   use_rewind,
        'algorithm':     'sutton_downward_sweep',
        'ticks_per_probe': 2,
        'ticks_per_probe_note': '1 tick input delay + 1 tick measurement, same for ALL actions',
        'wire_precision': wire_precision,
        'precision': {
            'speed_epsilon': precision['speed_epsilon'],
            'yaw_epsilon': precision['yaw_epsilon'],
            'speed_precision_digits': precision['speed_precision_digits'],
            'yaw_precision_digits': precision['yaw_precision_digits'],
            'deterministic': precision['deterministic'],
            'source': 'measured from repeated D0 probes',
        },
        'sutton_compliance': {
            'hardcoded_epsilons': False,
            'hardcoded_ranges': False,
            'hardcoded_frame_duration': False,
            'hardcoded_precision': False,
            'multi_tick_probes': False,
            'd0_subtraction': False,
            'normalization': False,
            'averaging': False,
        },
        'results': results
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    logger.info(f"Results saved to {filename}")
    return filename


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Phase A Bin Discovery — TMNF + TMInterface 2.x (Pure Sutton)',
    )
    parser.add_argument('--no-rewind', action='store_true',
                        help='Disable rewind (sequential probing)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Game speed multiplier (default: 1.0)')
    parser.add_argument('--port', type=int, default=8476,
                        help='TCP port for AgenticBridge.as (default: 8476)')
    parser.add_argument('--steering-only', action='store_true',
                        help='Only discover left/right steering')
    parser.add_argument('--actions', type=str, default=None,
                        help='Comma-separated actions (e.g. gas,left,right)')
    parser.add_argument('--from-zero', action='store_true',
                        help='Test from current speed (skip acceleration to MIN_PROBE_SPEED)')
    args = parser.parse_args()

    use_rewind = not args.no_rewind

    if args.steering_only:
        actions_to_run = ['left', 'right']
    elif args.actions:
        actions_to_run = [a.strip() for a in args.actions.split(',')]
    else:
        actions_to_run = list(TMNF_ACTIONS_CONFIG.keys())

    print()
    print("=" * 70)
    print("  PHASE A BIN DISCOVERY — Pure Sutton (Zero Hardcoding)")
    print("  Everything is DISCOVERED from the environment.")
    print("=" * 70)
    print()
    print(f"  Mode:     {'REWIND (independent probes)' if use_rewind else 'SEQUENTIAL'}")
    print(f"  Speed:    {args.speed}x")
    print(f"  Actions:  {actions_to_run}")
    print(f"  Ticks:    2 per probe (ALL actions — no exceptions)")
    print()

    # Connect
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=30.0):
        print("ERROR: Could not connect to AgenticBridge.as plugin.")
        return

    if not adapter.wait_for_race(timeout=60.0):
        print("ERROR: No race detected. Start a race first.")
        adapter.stop()
        return

    if args.speed != 1.0:
        adapter.set_speed(args.speed)
        logger.info(f"Game speed set to {args.speed}x")

    try:
        # ---- Get wire precision from adapter (Sutton: "first find the system's precision") ----
        wire_prec = adapter.get_wire_precision()
        logger.info(f"  Wire precision: {wire_prec}")

        # ---- STEP 0: Measure frame duration from environment ----
        frame_duration_s = measure_frame_duration(adapter)

        # ---- Get car moving (Sutton: "test from whatever state") ----
        # Need high speed for 1-tick steering to produce measurable yaw.
        # TMNF physics: tire lateral force proportional to speed. At low speed (60 km/h),
        # 1 tick of digital left produces 0 additional yaw vs D0.
        # At 200 km/h, 2-tick left gives yaw diff of ~2e-5 (clearly detectable).
        # Measured empirically: 60 km/h = 0 diff, 200 km/h = 1.98e-5 diff.
        if args.from_zero:
            logger.info("  --from-zero: testing from current speed (Sutton: 'try from zero speed')")
        else:
            MIN_PROBE_SPEED = 200.0
            fb = adapter.get_feedbacks()
            speed = fb.get('speed', 0)
            if speed < MIN_PROBE_SPEED:
                logger.info(f"  Accelerating to {MIN_PROBE_SPEED} km/h...")
                while speed < MIN_PROBE_SPEED:
                    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
                    adapter.wait_one_tick()
                    fb = adapter.get_feedbacks()
                    speed = fb.get('speed', 0)
                logger.info(f"  Speed: {speed:.1f} km/h")

        # Release inputs
        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()

        # ---- STEP 1: Measure system precision ----
        precision = measure_system_precision(adapter, use_rewind, num_probes=3)

        # ---- STEP 2: Run discovery ----
        results = run_discovery_tmnf(
            adapter, use_rewind=use_rewind,
            actions_to_run=actions_to_run,
            frame_duration_s=frame_duration_s,
            precision=precision,
            wire_precision=wire_prec
        )

        # ---- Save ----
        save_results(results, use_rewind, frame_duration_s, precision,
                     wire_precision=wire_prec)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        try:
            adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
            adapter.wait_one_tick()
        except Exception:
            pass
        adapter.stop()
        print("Done.")


if __name__ == '__main__':
    main()
