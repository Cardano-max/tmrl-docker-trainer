"""
PHASE A BIN DISCOVERY — TMNF + TMInterface 2.x (TCP bridge)

Pure Sutton algorithm with NO adaptations needed:
  - 10ms deterministic ticks (game pauses for us)
  - Rewind between probes: each probe starts from EXACT same state
  - No D0 subtraction (deterministic = no contamination)
  - No noise epsilon (no variance between probes)
  - One tick per probe
  - Full state: speed, velocity, yaw, forces, wheel contact

TMNF INPUT FACTS (without joystick/vJoy):
  - Gas:   BINARY only (>0.001 = full gas ON, else OFF)
  - Brake: BINARY only (>0.001 = full brake ON, else OFF)
  - Left:  BINARY keyboard key (InputType::Left, Linesight-RL method)
  - Right: BINARY keyboard key (InputType::Right, Linesight-RL method)

  NOTE: Analog steer (InputType::Steer, -65536..+65536) requires a joystick
  or vJoy binding. Without one, "Failed to execute input: no binding for
  Steer (analog) found." The "Convert Inputs to Analog Steering" TMInterface
  setting is a replay output formatter, NOT an input binding.

This means:
  - Gas discovery:   finds 2 bins (off vs on)
  - Brake discovery: finds 2 bins (off vs on)
  - Left discovery:  finds 2 bins (off vs on, measures yaw delta)
  - Right discovery: finds 2 bins (off vs on, measures yaw delta)

SETUP — REQUIRED BEFORE RUNNING:
  1. Install TMNF (free): https://trackmaniaforever.com/ or Steam
  2. Install TMInterface 2.x via ModLoader: https://donadigo.com/tminterface/
  3. Copy TMinterface/AgenticBridge.as to:
       %APPDATA%\\TMInterface\\Plugins\\AgenticBridge.as
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

# Input types are DISCOVERED by the algorithm, not assumed.
# The system probes each action and measures precision to determine
# whether each input is binary (2 bins) or analog (N bins).
# No "type" label in config — pure Sutton compliance.

TMNF_ACTIONS_CONFIG = {
    'gas': {
        'range': [0.0, 1.0],
        'description': 'Throttle (TMNF: binary >0.001 = full gas ON)'
    },
    'brake': {
        'range': [0.0, 1.0],
        'description': 'Brake (TMNF: binary >0.001 = full brake ON)'
    },
    'left': {
        'range': [0.0, 1.0],
        'description': 'Steer left (TMNF: binary keyboard key via InputType::Left)'
    },
    'right': {
        'range': [0.0, 1.0],
        'description': 'Steer right (TMNF: binary keyboard key via InputType::Right)'
    },
}

# NOTE: TMNF has NO analog steering without a joystick/vJoy binding.
# "Convert Inputs to Analog Steering" in TMInterface is a replay output setting,
# NOT an input binding. SetInputState(InputType::Steer) fails without a device.
# We use digital left/right (InputType::Left/Right) like Linesight-RL.
# The algorithm DISCOVERS that all 4 inputs are binary (2 bins each).


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

        # Build action — all inputs default to 0
        action_dict = {n: 0.0 for n in TMNF_ACTIONS_CONFIG}
        clipped = max(action_range[0], min(value, action_range[1]))
        action_dict[action_name] = clipped

        # For left/right steering probes: add gas to maintain speed
        # (yaw change requires speed; without gas, car decelerates and
        #  yaw changes become tiny/unmeasurable)
        is_steer = action_name in ('left', 'right')
        if is_steer:
            action_dict['gas'] = 1.0
            # Also ensure 'steering' is 0 (no analog steer attempt)
            action_dict['steering'] = 0.0

        # TMInterface has a ONE-TICK INPUT DELAY:
        # SetInputState during OnRunStep takes effect NEXT tick, not current.
        #
        # With rewind: rewind → send action → wait 1 tick (replayed inputs,
        #   same for all probes → consistent fb_before) → send action →
        #   wait N ticks (our input) → read fb_after.
        #
        # Steering (left/right): yaw change builds gradually, needs more ticks.
        # MEASURE_TICKS for steering: accumulates signal over N ticks because per-tick
        # yaw delta (~0.0002 rad) is below measurement_epsilon.
        # PLANNING IMPACT: steering bin deltas represent 5-tick effect, not 1-tick.
        # Planner must divide by MEASURE_TICKS to get per-tick delta if needed.
        MEASURE_TICKS = 5 if is_steer else 1

        if use_rewind:
            adapter.rewind()

        # Tick 1: send our action (loads for next tick).
        # With rewind, this tick uses replayed inputs (deterministic baseline).
        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()

        # Read state — consistent baseline with rewind, current state without.
        fb_before = adapter.get_feedbacks()

        # Tick 2+: our input takes effect
        for _ in range(MEASURE_TICKS):
            adapter.send_action_dict(action_dict)
            adapter.wait_one_tick()

        # Read state AFTER action
        fb_after = adapter.get_feedbacks()

        # Compute delta
        if is_steer:
            # Yaw change for left/right steering
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
            frame_duration_s=0.01,   # 10ms -- matches TMNF physics tick. TODO: use discovered value from adapter
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

    intelligence = ExperimentationIntelligence(TMNF_ACTIONS_CONFIG)
    intelligence.start_time = time.time()

    # With rewind: probes are deterministic (same starting state), so tight epsilon.
    # Without rewind: sequential drift needs larger epsilon.
    if use_rewind:
        EPSILON_GAS_BRAKE = 0.01   # Deterministic — only float precision matters
        EPSILON_STEER     = 1e-5   # Yaw precision over 5 ticks
    else:
        EPSILON_GAS_BRAKE = 0.05   # Absorbs sequential speed drift (~0.01/tick)
        EPSILON_STEER     = 1e-4   # Wider for drift

    logger.info("=" * 70)
    logger.info("PHASE A BIN DISCOVERY — TMNF (Pure Sutton)")
    logger.info("=" * 70)
    logger.info(f"  Tick:     10ms (deterministic)")
    logger.info(f"  Rewind:   {use_rewind}")
    logger.info(f"  Actions:  {actions_to_run}")
    logger.info(f"  Input types: discovered by algorithm (not assumed)")
    logger.info("")

    # Get starting state
    fb = adapter.get_feedbacks()
    logger.info(f"  Starting state: speed={fb.get('speed', 0):.2f} km/h, "
                f"pos=({fb.get('pos_x', 0):.1f}, {fb.get('pos_y', 0):.1f}, "
                f"{fb.get('pos_z', 0):.1f})")

    results = {}

    # Target speed for probing — need enough speed for all actions to show effect
    TARGET_SPEED = 15.0  # km/h

    for action_name in actions_to_run:
        if action_name not in TMNF_ACTIONS_CONFIG:
            logger.warning(f"  Skipping unknown action: {action_name}")
            continue

        # Re-accelerate before each action's discovery (sequential mode loses speed)
        if not use_rewind:
            fb = adapter.get_feedbacks()
            speed = fb.get('speed', 0)
            if speed < TARGET_SPEED:
                logger.info(f"  Re-accelerating from {speed:.1f} to {TARGET_SPEED} km/h...")
                while speed < TARGET_SPEED:
                    adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
                    adapter.wait_one_tick()
                    fb = adapter.get_feedbacks()
                    speed = fb.get('speed', 0)
                logger.info(f"  Speed restored: {speed:.1f} km/h")

        config = TMNF_ACTIONS_CONFIG[action_name]
        action_range = tuple(config['range'])
        is_bidir = action_range[0] < 0

        eps = EPSILON_STEER if action_name in ('left', 'right') else EPSILON_GAS_BRAKE

        disc = FrameBinDiscovery(
            action_name, action_range
        )
        disc.measurement_epsilon = eps

        logger.info(f"\n{'=' * 60}")
        logger.info(f"  DISCOVERING: {action_name}")
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
            # Build bins from discovered MIN/MAX
            # Binary detection: if MIN ≈ MAX (range < search_precision),
            # build_bins produces 2 bins (DEAD_ZONE + ON)
            bins = disc.build_bins()
            if is_bidir:
                bins = disc.make_bidirectional_bins(bins)

            # Infer input type from results (not from config)
            inferred_type = 'binary' if len(bins) <= 2 else 'analog'

            logger.info(f"\n  RESULT: {action_name}")
            logger.info(f"    MAX    = {a_max:.6f}")
            logger.info(f"    MIN    = {a_min:.6f}")
            logger.info(f"    Bins   = {len(bins)}")
            logger.info(f"    Probes = {probe_counter[0]}")
            logger.info(f"    Time   = {dt:.1f}s")
            logger.info(f"    Discovered type: {inferred_type}")

            results[action_name] = {
                'max':          a_max,
                'min':          a_min,
                'bins':         len(bins),
                'probes':       probe_counter[0],
                'time':         dt,
                'delta_max':    disc.delta_max,
                'delta_0':      disc.delta_0,
                'input_type':   inferred_type,
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

            results[action_name] = {
                'max':        None,
                'min':        None,
                'bins':       0,
                'probes':     probe_counter[0],
                'time':       dt,
                'delta_max':  disc.delta_max,
                'delta_0':    disc.delta_0,
                'input_type': 'none',
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
            logger.info(f"  {name}: NO RANGE (delta_max={r['delta_max']})")
        else:
            logger.info(f"  {name}: MIN={r['min']:.6f}, MAX={r['max']:.6f}, "
                        f"{r['bins']} bins, {r['probes']} probes "
                        f"[{r['input_type']}]")
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
        'plugin':        'AgenticBridge.as',
        'tick_ms':       10,
        'deterministic': True,
        'rewind_mode':   use_rewind,
        'algorithm':     'sutton_downward_sweep',
        'input_facts': {
            'gas':   'binary (threshold >0.001)',
            'brake': 'binary (threshold >0.001)',
            'left':  'binary keyboard key (InputType::Left)',
            'right': 'binary keyboard key (InputType::Right)',
            'note':  'analog steer (InputType::Steer) requires joystick/vJoy binding — not available',
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
                        help='TCP port for AgenticBridge.as plugin (default: 8476)')
    parser.add_argument('--steering-only', action='store_true',
                        help='Only run left/right steering discovery (skip gas/brake)')
    parser.add_argument('--actions', type=str, default=None,
                        help='Comma-separated actions to discover (e.g. gas,left,right)')
    args = parser.parse_args()

    use_rewind = not args.no_rewind

    # Determine which actions to discover
    if args.steering_only:
        actions_to_run = ['left', 'right']
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
    print("    3. AgenticBridge.as copied to TMInterface Plugins folder:")
    print("         %APPDATA%\\TMInterface\\Plugins\\AgenticBridge.as")
    print("    4. TMNF launched via TMInterface.exe")
    print("    5. A race is running (start any track)")
    print()
    print(f"  Mode:        {'REWIND (independent probes)' if use_rewind else 'SEQUENTIAL (no rewind)'}")
    print(f"  Game speed:  {args.speed}x")
    print(f"  Port:        {args.port}")
    print(f"  Actions:     {actions_to_run}")
    print()
    print("  Input types will be DISCOVERED by the algorithm (not assumed)")
    print()

    # Connect
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=30.0):
        print()
        print("ERROR: Could not connect to AgenticBridge.as plugin.")
        print()
        print("Troubleshooting:")
        print("  1. Is TMNF running via TMInterface.exe?")
        print("  2. Is AgenticBridge.as in the Plugins folder?")
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
        # System initialization (Sutton section 9): get car moving
        # "Speed starts at 100" — car must be moving before experimentation
        MIN_PROBE_SPEED = 10.0  # km/h — moderate speed (grass has high friction)
        fb = adapter.get_feedbacks()
        speed = fb.get('speed', 0)
        if speed < MIN_PROBE_SPEED:
            logger.info(f"  System init: accelerating from {speed:.1f} to {MIN_PROBE_SPEED} km/h...")
            while speed < MIN_PROBE_SPEED:
                adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
                adapter.wait_one_tick()
                fb = adapter.get_feedbacks()
                speed = fb.get('speed', 0)
            logger.info(f"  System init complete: speed={speed:.1f} km/h")

        # Release inputs before discovery
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
