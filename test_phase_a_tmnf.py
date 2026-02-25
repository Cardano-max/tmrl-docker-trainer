"""
PHASE A BIN DISCOVERY — TMNF + TMInterface 2.x (TCP bridge)

Pure Sutton algorithm with NO adaptations needed:
  - 10ms deterministic ticks (game pauses for us)
  - Rewind between probes: each probe starts from EXACT same state
  - No D0 subtraction (deterministic = no contamination)
  - No noise epsilon (no variance between probes)
  - One tick per probe
  - Full state: speed, velocity, yaw, forces, wheel contact

TMNF INPUT FACTS:
  - Gas:      BINARY only (>0.001 = full gas ON, else OFF)
  - Brake:    BINARY only (>0.001 = full brake ON, else OFF)
  - Steering: ANALOG -1.0 to +1.0 (maps to -65536..+65536 in TMInterface)

This means:
  - Gas discovery: trivial (finds 2 bins — off vs on)
  - Brake discovery: trivial (finds 2 bins — off vs on)
  - Steering discovery: full Sutton sweep (finds ~20+ bins)

SETUP — REQUIRED BEFORE RUNNING:
  1. Install TMNF (free): https://trackmaniaforever.com/ or Steam
  2. Install TMInterface 2.x via ModLoader: https://donadigo.com/tminterface/
  3. Copy TMinterface/SuttonBridge.as to:
       %APPDATA%\\TMInterface\\Plugins\\SuttonBridge.as
  4. Launch TMNF via TMInterface.exe
  5. Start a race on any track (wait for countdown to end)
  6. Run this script

USAGE:
  python test_phase_a_tmnf.py
  python test_phase_a_tmnf.py --no-rewind    # Sequential probes (no rewind)
  python test_phase_a_tmnf.py --speed 5.0    # Run game at 5x speed
  python test_phase_a_tmnf.py --port 8476    # Custom port (default: 8476)
  python test_phase_a_tmnf.py --steering-only # Only run steering discovery
"""

import sys
import os
import json
import time
import logging
import argparse
import math
from datetime import datetime

# Add project root to path
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
# ACTIONS CONFIG (TMNF reality)
# =============================================================================

# TMNF inputs:
#   gas:      BINARY. Full gas or nothing. No analog throttle.
#             Discovery will find 2 bins: [0, off/on threshold] and [threshold, 1.0]
#   brake:    BINARY. Full brake or nothing. Discovery finds 2 bins.
#   steering: ANALOG -1.0 to +1.0. Full Sutton sweep expected.
#             With bidirectional bins: ~21+ bins (symmetric around 0).

TMNF_ACTIONS_CONFIG = {
    'gas': {
        'range': [0.0, 1.0],
        'type': 'binary',
        'description': 'Throttle — BINARY in TMNF (>0.001 = full gas ON)'
    },
    'brake': {
        'range': [0.0, 1.0],
        'type': 'binary',
        'description': 'Brake — BINARY in TMNF (>0.001 = full brake ON)'
    },
    'steering': {
        'range': [-1.0, 1.0],
        'type': 'analog',
        'description': 'Steering — ANALOG (-1=full left, +1=full right)'
    }
}


# =============================================================================
# PROBE FUNCTION
# =============================================================================

def make_probe_fn(
    adapter: TMNFAdapter,
    disc: 'FrameBinDiscovery',
    action_name: str,
    action_range: tuple,
    use_rewind: bool,
    probe_counter: list,
    intelligence: 'ExperimentationIntelligence',
) -> callable:
    """
    Returns a probe_one_tick function for the given action.

    Pure Sutton: one tick = one probe. No D0. No multi-frame. No averaging.

    With rewind=True:  rewind to saved state before each probe.
    With rewind=False: probe sequentially (car state accumulates).

    Delta for gas/brake:  speed_after - speed_before (signed km/h change)
    Delta for steering:   yaw_after - yaw_before (wrapped to [-pi, pi])
    """
    def probe_one_tick(value: float) -> 'ProbeResult':
        nonlocal probe_counter

        if use_rewind:
            # Rewind to saved state so each probe is independent
            adapter.rewind()

        # Read state BEFORE applying action
        fb_before = adapter.get_feedbacks()

        # Apply action for exactly one tick
        action_dict = {n: 0.0 for n in TMNF_ACTIONS_CONFIG}
        clipped = max(action_range[0], min(value, action_range[1]))
        action_dict[action_name] = clipped

        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()

        # Read state AFTER action
        fb_after = adapter.get_feedbacks()

        # Compute delta
        if action_name == 'steering':
            # Yaw change (direct from TMInterface — no position-based approximation needed)
            if 'yaw' in fb_before and 'yaw' in fb_after:
                delta = fb_after['yaw'] - fb_before['yaw']
                # Wrap to [-pi, pi]
                while delta > math.pi:
                    delta -= 2 * math.pi
                while delta < -math.pi:
                    delta += 2 * math.pi
            else:
                delta = 0.0
        else:
            # Speed change (km/h) — positive = accelerating, negative = braking
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
            action_value=clipped,
            delta_state=delta,
            feedback_before=fb_before,
            feedback_after=fb_after,
            frame_duration_s=0.01,   # 10ms
            valid=True
        )
        disc.probes.append(pr)
        return pr

    return probe_one_tick


# =============================================================================
# DISCOVERY
# =============================================================================

def run_discovery_tmnf(adapter: TMNFAdapter, use_rewind: bool = True,
                       actions_to_run: list = None):
    """
    Run Sutton's bin discovery algorithm on TMNF.

    With rewind=True (default): each probe starts from the EXACT same state.
    Pong-like: delta depends ONLY on action value, not accumulated state.
    No D0 subtraction, no noise epsilon — pure deterministic Sutton.

    With rewind=False: sequential probing (car accumulates state).
    Closer to TM2020 mode; still deterministic.

    Args:
        adapter:        Connected TMNFAdapter
        use_rewind:     True = independent probes, False = sequential
        actions_to_run: List of action names to discover (default: all 3)

    Returns:
        Dict of {action_name: result_dict}
    """
    if actions_to_run is None:
        actions_to_run = list(TMNF_ACTIONS_CONFIG.keys())

    intelligence = ExperimentationIntelligence(TMNF_ACTIONS_CONFIG, change_threshold=0.001)
    intelligence.start_time = time.time()

    # With deterministic environment: no noise floor needed.
    # Only need float precision epsilon for game's float output.
    EPSILON_GAS_BRAKE = 1e-6    # Gas/brake are binary — any delta above this is real
    EPSILON_STEERING  = 1e-5    # Steering yaw change precision

    logger.info("=" * 70)
    logger.info("PHASE A BIN DISCOVERY — TMNF (Pure Sutton)")
    logger.info("=" * 70)
    logger.info(f"  Tick:     10ms (deterministic)")
    logger.info(f"  Rewind:   {use_rewind}")
    logger.info(f"  Actions:  {actions_to_run}")
    logger.info(f"  Gas/brake input: BINARY (2 bins expected each)")
    logger.info(f"  Steering input:  ANALOG (full sweep expected)")
    logger.info("")

    # Get starting state
    fb = adapter.get_feedbacks()
    logger.info(f"  Starting state: speed={fb.get('speed', 0):.2f} km/h, "
                f"pos=({fb.get('pos_x', 0):.1f}, {fb.get('pos_y', 0):.1f}, "
                f"{fb.get('pos_z', 0):.1f})")

    results = {}

    for action_name in actions_to_run:
        if action_name not in TMNF_ACTIONS_CONFIG:
            logger.warning(f"  Skipping unknown action: {action_name}")
            continue

        config = TMNF_ACTIONS_CONFIG[action_name]
        action_range = tuple(config['range'])
        is_bidir = action_range[0] < 0

        eps = EPSILON_STEERING if action_name == 'steering' else EPSILON_GAS_BRAKE

        disc = FrameBinDiscovery(
            action_name, action_range,
            search_precision=0.001,
            noise_epsilon=eps,
            signal_epsilon=eps
        )

        logger.info(f"\n{'=' * 60}")
        logger.info(f"  DISCOVERING: {action_name}")
        logger.info(f"  Type:    {config['type']}")
        logger.info(f"  Range:   {action_range}")
        logger.info(f"  Epsilon: {eps}")
        logger.info(f"  Rewind:  {use_rewind}")
        logger.info(f"{'=' * 60}")

        # Save state before this action's discovery
        if use_rewind:
            adapter.save_state()
            logger.info("  State saved for rewind-based probing")

        probe_counter = [0]
        t0 = time.time()

        probe_fn = make_probe_fn(
            adapter, disc, action_name, action_range,
            use_rewind, probe_counter, intelligence
        )

        # Run Sutton's downward sweep + binary search
        a_max, a_min = disc.run_discovery(probe_fn)

        dt = time.time() - t0

        if a_max is not None and a_min is not None:
            bins = disc.build_bins()
            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

            logger.info(f"\n  RESULT: {action_name}")
            logger.info(f"    MAX    = {a_max:.6f}")
            logger.info(f"    MIN    = {a_min:.6f}")
            logger.info(f"    Bins   = {len(bins)}")
            logger.info(f"    Probes = {probe_counter[0]}")
            logger.info(f"    Time   = {dt:.1f}s")
            logger.info(f"    Input type: {config['type']}")
            if config['type'] == 'binary':
                logger.info(f"    (Binary input: expect 2 bins)")

            results[action_name] = {
                'max':          a_max,
                'min':          a_min,
                'bins':         len(bins),
                'probes':       probe_counter[0],
                'time':         dt,
                'delta_max':    disc.delta_max,
                'delta_0':      disc.delta_0,
                'input_type':   config['type'],
                'bin_details': [
                    {'id': b.bin_id, 'min': b.a_min, 'max': b.a_max, 'label': b.label}
                    for b in bins
                ]
            }
        else:
            logger.warning(f"\n  RESULT: {action_name} — NO DETECTABLE RANGE")
            logger.warning(f"    delta_max = {disc.delta_max}")
            logger.warning(f"    delta_0   = {disc.delta_0}")
            logger.warning(f"    Probes    = {probe_counter[0]}")
            logger.warning(f"    (If gas/brake: expected for binary — no gradient between 0 and 1)")

            results[action_name] = {
                'max':        None,
                'min':        None,
                'bins':       0,
                'probes':     probe_counter[0],
                'time':       dt,
                'delta_max':  disc.delta_max,
                'delta_0':    disc.delta_0,
                'input_type': config['type'],
                'no_range':   True
            }

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("PHASE A COMPLETE — TMNF")
    logger.info("=" * 70)
    total_probes = sum(r['probes'] for r in results.values())
    total_time   = sum(r['time'] for r in results.values())
    logger.info(f"  Total probes: {total_probes}")
    logger.info(f"  Total time:   {total_time:.1f}s")
    logger.info(f"  Rewind mode:  {use_rewind}")
    for name, r in results.items():
        if r.get('no_range'):
            logger.info(f"  {name}: NO RANGE (delta_max={r['delta_max']}, "
                        f"type={r['input_type']})")
        else:
            logger.info(f"  {name}: MIN={r['min']:.6f}, MAX={r['max']:.6f}, "
                        f"{r['bins']} bins, {r['probes']} probes [{r['input_type']}]")
    logger.info("=" * 70)

    return results


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_results(results: dict, use_rewind: bool) -> str:
    """Save discovery results to JSON file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"tmnf_phase_a_results_{timestamp}.json"

    output = {
        'timestamp':     timestamp,
        'environment':   'TMNF',
        'interface':     'TMInterface 2.x (TCP bridge)',
        'plugin':        'SuttonBridge.as',
        'tick_ms':       10,
        'deterministic': True,
        'rewind_mode':   use_rewind,
        'algorithm':     'sutton_downward_sweep',
        'input_facts': {
            'gas':      'binary (threshold >0.001)',
            'brake':    'binary (threshold >0.001)',
            'steering': 'analog -65536..+65536',
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
        description='Phase A Bin Discovery — TMNF + TMInterface 2.x',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_phase_a_tmnf.py                 # Full discovery, rewind mode
  python test_phase_a_tmnf.py --no-rewind     # Sequential (no rewind)
  python test_phase_a_tmnf.py --speed 5.0     # 5x game speed
  python test_phase_a_tmnf.py --steering-only # Only steering discovery
  python test_phase_a_tmnf.py --port 8476     # Custom port
        """
    )
    parser.add_argument('--no-rewind', action='store_true',
                        help='Disable rewind (sequential probing, car state accumulates)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Game speed multiplier (default: 1.0)')
    parser.add_argument('--port', type=int, default=8476,
                        help='TCP port for SuttonBridge.as plugin (default: 8476)')
    parser.add_argument('--steering-only', action='store_true',
                        help='Only run steering discovery (skip gas/brake)')
    parser.add_argument('--actions', type=str, default=None,
                        help='Comma-separated actions to discover (e.g. gas,steering)')
    args = parser.parse_args()

    use_rewind = not args.no_rewind

    # Determine which actions to discover
    if args.steering_only:
        actions_to_run = ['steering']
    elif args.actions:
        actions_to_run = [a.strip() for a in args.actions.split(',')]
    else:
        actions_to_run = list(TMNF_ACTIONS_CONFIG.keys())

    print()
    print("=" * 70)
    print("  PHASE A BIN DISCOVERY — TMNF + TMInterface 2.x")
    print("  Pure Sutton Algorithm (deterministic, 10ms ticks)")
    print("=" * 70)
    print()
    print("  Prerequisites:")
    print("    1. TMNF installed (free game)")
    print("    2. TMInterface 2.x installed via ModLoader")
    print("    3. SuttonBridge.as copied to TMInterface Plugins folder:")
    print("         %APPDATA%\\TMInterface\\Plugins\\SuttonBridge.as")
    print("    4. TMNF launched via TMInterface.exe")
    print("    5. A race is running (start any track)")
    print()
    print(f"  Mode:        {'REWIND (independent probes)' if use_rewind else 'SEQUENTIAL (no rewind)'}")
    print(f"  Game speed:  {args.speed}x")
    print(f"  Port:        {args.port}")
    print(f"  Actions:     {actions_to_run}")
    print()
    print("  TMNF input facts:")
    print("    Gas:      BINARY (2 bins expected)")
    print("    Brake:    BINARY (2 bins expected)")
    print("    Steering: ANALOG (full sweep, ~21+ bins expected)")
    print()

    # Connect
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=30.0):
        print()
        print("ERROR: Could not connect to SuttonBridge.as plugin.")
        print()
        print("Troubleshooting:")
        print("  1. Is TMNF running via TMInterface.exe?")
        print("  2. Is SuttonBridge.as in the Plugins folder?")
        print(f"  3. Is port {args.port} correct?")
        print("     (Change with RegisterVariable custom_port in TMInterface console)")
        print()
        print("Setup guide: docs/TMNF_SETUP.md")
        return

    # Wait for race
    if not adapter.wait_for_race(timeout=60.0):
        print()
        print("ERROR: No race detected.")
        print("Start a solo race in TMNF, then run this script.")
        adapter.stop()
        return

    # Set game speed
    if args.speed != 1.0:
        adapter.set_speed(args.speed)
        logger.info(f"Game speed set to {args.speed}x")

    try:
        # Neutral state (release all inputs)
        adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
        adapter.wait_one_tick()

        # Run discovery
        results = run_discovery_tmnf(adapter, use_rewind=use_rewind,
                                     actions_to_run=actions_to_run)

        # Save results
        save_results(results, use_rewind)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        # Release all controls
        try:
            adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
            adapter.wait_one_tick()
        except Exception:
            pass
        adapter.stop()
        print()
        print("Done.")


if __name__ == '__main__':
    main()
