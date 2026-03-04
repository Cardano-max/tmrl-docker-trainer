"""
5-RUN VALIDATION: Pure Sutton Single-Algorithm Discovery

Validates the rewritten run_discovery() that uses ONE algorithm for all actions.
No pre-classification, no separate binary path, no wire precision dependency.

Nature (binary/analog) is DISCOVERED by the exponential sweep:
  - Saturated -> D0 directly = BINARY (combined bracket, MAX=MIN)
  - Saturated -> intermediate -> D0 = ANALOG (separate brackets)

Expected TMNF results (all binary inputs):
  - Gas:   MAX = MIN (threshold), nature=binary
  - Brake: MAX = MIN (threshold), nature=binary
  - Left:  MAX = MIN (threshold), nature=binary
  - Right: MAX = MIN (threshold), nature=binary
  - All 5 runs identical (deterministic rewind)

USAGE:
  python run_5_pure_sutton.py
  python run_5_pure_sutton.py --port 8476 --speed 5.0
  python run_5_pure_sutton.py --runs 3 --actions gas,brake
"""

import sys
import os
import json
import time
import math
import logging
import argparse
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
logger = logging.getLogger('PURE_SUTTON')


# =============================================================================
# ACTIONS CONFIG
# =============================================================================

TMNF_ACTIONS_CONFIG = {
    'gas':   {'description': 'Throttle'},
    'brake': {'description': 'Brake'},
    'left':  {'description': 'Steer left (digital key)'},
    'right': {'description': 'Steer right (digital key)'},
}


# =============================================================================
# PROBE FUNCTION (reused from test_phase_a_tmnf.py)
# =============================================================================

def make_probe_fn(adapter, disc, action_name, use_rewind, probe_counter,
                  intelligence, frame_duration_s):
    """Returns a probe function for the given action.

    ALL actions use exactly 2 ticks (1 frame = 1 probe):
      Tick 1: send action (loads for next tick due to TMInterface input delay)
      Tick 2: action takes effect, read fb_after
    """
    def probe_one_tick(value):
        nonlocal probe_counter

        action_dict = {n: 0.0 for n in TMNF_ACTIONS_CONFIG}
        action_dict[action_name] = value

        is_steer = action_name in ('left', 'right')
        if is_steer:
            action_dict['gas'] = 1.0
            action_dict['steering'] = 0.0

        if use_rewind:
            adapter.rewind()

        # Tick 1: send action (input delay)
        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()
        fb_before = adapter.get_feedbacks()

        # Tick 2: action takes effect
        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()
        fb_after = adapter.get_feedbacks()

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
# SINGLE RUN
# =============================================================================

def run_single_discovery(adapter, run_num, actions_to_run, use_rewind,
                         frame_duration_s, precision):
    """Run one complete discovery cycle for all actions."""
    logger.info(f"\n{'=' * 70}")
    logger.info(f"  RUN {run_num} -- Pure Sutton Single Algorithm")
    logger.info(f"{'=' * 70}")

    intelligence = ExperimentationIntelligence(TMNF_ACTIONS_CONFIG)
    intelligence.start_time = time.time()

    if use_rewind:
        # Rewind to the state saved by main() (at 200 km/h) so every run
        # starts from the EXACT same state.  Without this, the car drifts
        # between runs and steering deltas become undetectable.
        adapter.rewind()
        adapter.wait_one_tick()   # let _state_bytes sync
        adapter.save_state()      # re-save as probe restore point
        logger.info("  State restored & saved for this run")

    results = {}

    for action_name in actions_to_run:
        is_steer = action_name in ('left', 'right')
        eps = precision['yaw_epsilon'] if is_steer else precision['speed_epsilon']

        disc = FrameBinDiscovery(
            action_name,
            search_precision=eps,
            measurement_epsilon=eps
        )

        probe_counter = [0]
        t0 = time.time()

        probe_fn = make_probe_fn(
            adapter, disc, action_name,
            use_rewind, probe_counter, intelligence,
            frame_duration_s
        )

        # Pure Sutton: no wire_precision, no pre-classification
        a_max, a_min = disc.run_discovery(probe_fn)

        dt = time.time() - t0
        nature = disc.nature or 'unknown'

        if a_max is not None and a_min is not None:
            bins = disc.build_bins()
            results[action_name] = {
                'max': a_max,
                'min': a_min,
                'bins': len(bins),
                'probes': probe_counter[0],
                'time': dt,
                'delta_max': disc.delta_max,
                'delta_0': disc.delta_0,
                'nature': nature,
                'max_eq_min': abs(a_max - a_min) < (eps or 1e-10),
                'bin_details': [
                    {'id': b.bin_id, 'min': b.a_min, 'max': b.a_max, 'label': b.label}
                    for b in bins
                ],
                'probe_data': [
                    {
                        'action_value': p.action_value,
                        'delta': p.delta_state,
                    }
                    for p in disc.probes
                ]
            }
        else:
            results[action_name] = {
                'max': None, 'min': None, 'bins': 0,
                'probes': probe_counter[0], 'time': dt,
                'delta_max': disc.delta_max, 'delta_0': disc.delta_0,
                'nature': nature, 'max_eq_min': False,
                'no_range': True
            }

    return results


# =============================================================================
# MEASURE FRAME DURATION + PRECISION (from test_phase_a_tmnf.py)
# =============================================================================

def measure_frame_duration(adapter):
    """Discover frame duration from environment."""
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
        delta_ms = 10
    return delta_ms / 1000.0


def measure_system_precision(adapter, use_rewind, num_probes=3):
    """Discover measurement precision by probing D0 multiple times."""
    if use_rewind:
        adapter.save_state()

    speed_deltas = []
    yaw_deltas = []

    for i in range(num_probes):
        if use_rewind:
            adapter.rewind()

        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()
        fb_before = adapter.get_feedbacks()

        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()
        fb_after = adapter.get_feedbacks()

        speed_deltas.append(fb_after.get('speed', 0) - fb_before.get('speed', 0))
        yaw_deltas.append(fb_after.get('yaw', 0) - fb_before.get('yaw', 0))

    def max_variance(values):
        if len(values) < 2:
            return 0.0
        return max(abs(a - b) for i, a in enumerate(values) for b in values[i+1:])

    speed_var = max_variance(speed_deltas)
    yaw_var = max_variance(yaw_deltas)

    import sys as _sys
    eps = _sys.float_info.epsilon

    speed_epsilon = speed_var * 2.0 if speed_var > 0 else max(abs(speed_deltas[0]) * eps * 10, 1e-15)
    yaw_epsilon = yaw_var * 2.0 if yaw_var > 0 else max(abs(yaw_deltas[0]) * eps * 10, 1e-15)

    return {
        'speed_epsilon': speed_epsilon,
        'yaw_epsilon': yaw_epsilon,
        'deterministic': (speed_var == 0.0 and yaw_var == 0.0),
    }


# =============================================================================
# SUMMARY TABLE
# =============================================================================

def print_summary(all_runs, actions_to_run):
    """Print a compact terminal summary table."""
    print()
    print("=" * 90)
    print("  PURE SUTTON DISCOVERY -- 5-RUN VALIDATION SUMMARY")
    print("=" * 90)
    print()

    # Per-action table
    header = f"{'Action':<8} {'Run':>4} {'Nature':<8} {'MAX':>14} {'MIN':>14} {'MAX=MIN':>8} {'Bins':>5} {'Probes':>7} {'Time':>7}"
    print(header)
    print("-" * len(header))

    for action in actions_to_run:
        for run_idx, run_results in enumerate(all_runs, 1):
            r = run_results.get(action, {})
            if r.get('no_range'):
                print(f"{action:<8} {run_idx:>4} {'none':<8} {'N/A':>14} {'N/A':>14} {'N/A':>8} {0:>5} {r.get('probes', 0):>7} {r.get('time', 0):>6.1f}s")
            else:
                a_max = r.get('max', 0)
                a_min = r.get('min', 0)
                nature = r.get('nature', '?')
                max_eq = 'YES' if r.get('max_eq_min') else 'no'
                print(f"{action:<8} {run_idx:>4} {nature:<8} {a_max:>14.10g} {a_min:>14.10g} {max_eq:>8} {r.get('bins', 0):>5} {r.get('probes', 0):>7} {r.get('time', 0):>6.1f}s")
        print()

    # Cross-run stability
    print("=" * 90)
    print("  CROSS-RUN STABILITY")
    print("=" * 90)
    print()

    all_stable = True
    for action in actions_to_run:
        maxs = [r.get(action, {}).get('max') for r in all_runs if r.get(action, {}).get('max') is not None]
        mins = [r.get(action, {}).get('min') for r in all_runs if r.get(action, {}).get('min') is not None]
        natures = [r.get(action, {}).get('nature') for r in all_runs if r.get(action, {}).get('nature')]

        max_stable = len(set(maxs)) <= 1 if maxs else False
        min_stable = len(set(mins)) <= 1 if mins else False
        nature_stable = len(set(natures)) <= 1 if natures else False

        max_verdict = "IDENTICAL" if max_stable else f"VARIES ({max(maxs) - min(maxs):.10g})" if maxs else "N/A"
        min_verdict = "IDENTICAL" if min_stable else f"VARIES ({max(mins) - min(mins):.10g})" if mins else "N/A"
        nature_verdict = "IDENTICAL" if nature_stable else f"VARIES ({set(natures)})"

        if not (max_stable and min_stable and nature_stable):
            all_stable = False

        print(f"  {action}:")
        print(f"    MAX:    {max_verdict}")
        print(f"    MIN:    {min_verdict}")
        print(f"    Nature: {nature_verdict}")

    print()
    print(f"  Overall: {'ALL STABLE -- DETERMINISTIC' if all_stable else 'VARIANCE DETECTED'}")
    print()

    # Key finding
    print("=" * 90)
    print("  KEY FINDING: MAX = MIN for binary actions?")
    print("=" * 90)
    for action in actions_to_run:
        max_eq_results = [r.get(action, {}).get('max_eq_min', False) for r in all_runs]
        all_eq = all(max_eq_results)
        print(f"  {action}: MAX=MIN in {sum(max_eq_results)}/{len(max_eq_results)} runs -- {'PASS' if all_eq else 'FAIL'}")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='5-Run Validation: Pure Sutton Single-Algorithm Discovery'
    )
    parser.add_argument('--port', type=int, default=8476, help='TMInterface TCP port')
    parser.add_argument('--speed', type=float, default=1.0, help='Game speed multiplier')
    parser.add_argument('--runs', type=int, default=5, help='Number of runs (default: 5)')
    parser.add_argument('--actions', type=str, default=None,
                        help='Comma-separated actions (default: gas,brake,left,right)')
    parser.add_argument('--no-rewind', action='store_true', help='Disable rewind')
    args = parser.parse_args()

    use_rewind = not args.no_rewind
    actions_to_run = [a.strip() for a in args.actions.split(',')] if args.actions else list(TMNF_ACTIONS_CONFIG.keys())

    print()
    print("=" * 70)
    print("  PURE SUTTON DISCOVERY -- 5-RUN VALIDATION")
    print("  Single algorithm, no pre-classification, no wire precision")
    print("=" * 70)
    print()
    print(f"  Runs:    {args.runs}")
    print(f"  Actions: {actions_to_run}")
    print(f"  Rewind:  {use_rewind}")
    print(f"  Speed:   {args.speed}x")
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

    try:
        # Measure frame duration
        frame_duration_s = measure_frame_duration(adapter)
        logger.info(f"Frame duration: {frame_duration_s*1000:.0f}ms")

        # Accelerate to 200 km/h
        MIN_PROBE_SPEED = 200.0
        fb = adapter.get_feedbacks()
        speed = fb.get('speed', 0)
        if speed < MIN_PROBE_SPEED:
            logger.info(f"Accelerating to {MIN_PROBE_SPEED} km/h...")
            while speed < MIN_PROBE_SPEED:
                adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
                adapter.wait_one_tick()
                fb = adapter.get_feedbacks()
                speed = fb.get('speed', 0)
            logger.info(f"Speed: {speed:.1f} km/h")

        # Release inputs
        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()

        # Measure precision
        precision = measure_system_precision(adapter, use_rewind)
        logger.info(f"Precision: speed_eps={precision['speed_epsilon']:.15g}, "
                    f"yaw_eps={precision['yaw_epsilon']:.15g}, "
                    f"deterministic={precision['deterministic']}")

        # Save state at speed for all runs
        if use_rewind:
            adapter.save_state()
            logger.info("State saved at speed for all runs")

        # Run discovery N times
        all_runs = []
        t_total_start = time.time()

        for run_num in range(1, args.runs + 1):
            results = run_single_discovery(
                adapter, run_num, actions_to_run, use_rewind,
                frame_duration_s, precision
            )
            all_runs.append(results)

        t_total = time.time() - t_total_start

        # Print summary
        print_summary(all_runs, actions_to_run)

        # Save JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output = {
            'timestamp': timestamp,
            'algorithm': 'pure_sutton_single_algorithm',
            'algorithm_version': 'quick-14',
            'description': 'Single exponential sweep discovers nature (binary/analog) '
                          'organically. No pre-classification, no wire precision.',
            'environment': 'TMNF',
            'interface': 'TMInterface 2.x (TCP bridge)',
            'frame_duration_ms': frame_duration_s * 1000,
            'deterministic': precision['deterministic'],
            'rewind_mode': use_rewind,
            'num_runs': args.runs,
            'total_time_s': t_total,
            'precision': precision,
            'runs': [
                {'run': i + 1, 'results': r}
                for i, r in enumerate(all_runs)
            ],
        }

        filename = f"validation_pure_sutton_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        logger.info(f"Results saved to {filename}")
        print(f"  JSON: {filename}")
        print(f"  Total time: {t_total:.1f}s ({t_total/args.runs:.1f}s per run)")

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
