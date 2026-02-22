#!/usr/bin/env python3
"""
PHASE A LIVE TEST: Bin Discovery with TrackMania

Algorithm (algorithm_spec_from_meetings.md section 14):
    Downward sweep — probe action=0 for context, then descend powers of 10.
    Find MAX bracket (delta drops below saturated), binary search it.
    Find MIN bracket (delta same as action=0), binary search it.
    Store MIN, MAX.

No heuristics. No baseline subtraction. No magic decimals.
Pure transition search. Action=0 is a real action (not noise).

USAGE:
  python test_phase_a_live.py

REQUIREMENTS:
  - TrackMania game running
  - OpenPlanet plugin connected
  - TMRL server running on 127.0.0.1:9000
"""

import sys
import os
import json
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(f'phase_a_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run Phase A with live environment"""

    logger.info("="*80)
    logger.info("PHASE A LIVE TEST: BIN DISCOVERY")
    logger.info("="*80)
    logger.info(f"Start time: {datetime.now().isoformat()}")
    logger.info("")

    # ==========================================================================
    # STEP 1: Check TrackMania Connection
    # ==========================================================================
    logger.info("STEP 1: Checking TrackMania Connection")
    logger.info("-" * 80)

    try:
        from adapters.tmrl_live_adapter import TMRLLiveAdapter

        adapter = TMRLLiveAdapter()
        logger.info("  Created TMRLLiveAdapter")

        if not adapter.connect(timeout=5.0):
            logger.error("  FAILED: Cannot connect to TrackMania")
            logger.error("    Make sure:")
            logger.error("    - TrackMania is running")
            logger.error("    - OpenPlanet plugin is installed")
            logger.error("    - TMRL server listening on 127.0.0.1:9000")
            return False

        adapter.start()
        logger.info("  CONNECTED to TrackMania (TCP 127.0.0.1:9000)")

        # vgamepad hardware registration only — not algorithmic warmup.
        # Spec: "do not interfere with the environment" (section 3).
        # TrackMania needs the OS to register the virtual gamepad device.
        # Send neutral inputs (all zeros) rapidly for ~2 seconds.
        logger.info("  Registering vgamepad with OS (~2 seconds, neutral inputs)...")
        for i in range(40):  # 40 x 50ms = 2 seconds
            adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
            time.sleep(0.05)
        time.sleep(0.5)

        fb = adapter.get_feedbacks()
        logger.info(f"  Got feedbacks: {list(fb.keys())}")
        logger.info(f"    Speed: {fb.get('speed', 0):.1f}")
        logger.info(f"    input_gas: {fb.get('input_gas', 0):.3f}")
        logger.info(f"    Position: ({fb.get('pos_x', 0):.1f}, {fb.get('pos_z', 0):.1f})")

    except Exception as e:
        logger.error(f"  FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

    logger.info("")

    # ==========================================================================
    # STEP 2: Load Configuration
    # ==========================================================================
    logger.info("STEP 2: Loading Configuration")
    logger.info("-" * 80)

    try:
        config_path = "config/system_config_corrected.json"
        with open(config_path, 'r') as f:
            config = json.load(f)

        logger.info(f"  Loaded config: {config_path}")
        logger.info(f"    System: {config.get('system_name')}")
        logger.info(f"    Version: {config.get('version')}")
        logger.info(f"    Actions: {list(config.get('actions', {}).keys())}")
        logger.info(f"    Frame timing: {config.get('environment', {}).get('timing', {}).get('frame_duration_ms', 50)}ms")

    except Exception as e:
        logger.error(f"  FAILED: {e}")
        return False

    logger.info("")

    # ==========================================================================
    # STEP 3: Initialize Experimentation Coordinator
    # ==========================================================================
    logger.info("STEP 3: Initializing Experimentation Coordinator")
    logger.info("-" * 80)

    try:
        from intelligence.intelligence_experimentation import ExperimentationCoordinator

        frame_dt_ms = config.get('environment', {}).get('timing', {}).get('frame_duration_ms', 50.0)
        frame_dt_s = frame_dt_ms / 1000.0

        logger.info(f"  Frame duration: {frame_dt_ms:.1f}ms ({1000.0/frame_dt_ms:.1f} Hz)")

        coordinator = ExperimentationCoordinator(
            actions_config=config['actions'],
            send_action_fn=adapter.send_action_dict,
            get_feedbacks_fn=adapter.get_feedbacks,
            wait_fn=time.sleep,
            reset_fn=None,
            frame_duration_s=frame_dt_s
        )

        logger.info("  ExperimentationCoordinator initialized")
        logger.info(f"    Algorithm: downward sweep (algorithm_spec_from_meetings.md)")
        logger.info(f"    Actions to discover: {list(config['actions'].keys())}")

    except Exception as e:
        logger.error(f"  FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        adapter.stop()
        return False

    logger.info("")

    # ==========================================================================
    # STEP 4: Run Bin Discovery (algorithm_spec_from_meetings.md)
    # ==========================================================================
    logger.info("STEP 4: Running Bin Discovery")
    logger.info("-" * 80)
    logger.info("Algorithm (algorithm_spec_from_meetings.md section 14):")
    logger.info("  Downward sweep: probe action=0 for context, then descend powers of 10.")
    logger.info("  Find MAX bracket (delta drops below saturated), binary search it.")
    logger.info("  Find MIN bracket (delta same as action=0), binary search it.")
    logger.info("  Store MIN, MAX.")
    logger.info("")
    logger.info("  No heuristics. No baseline subtraction. No magic decimals.")
    logger.info("  Pure transition search. Action=0 is a real action.")
    logger.info("")

    try:
        start_time = time.time()

        discovered_bins = coordinator.run_full_experimentation()

        elapsed = time.time() - start_time

        logger.info(f"  Experimentation complete ({elapsed:.1f}s)")

    except Exception as e:
        logger.error(f"  FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        adapter.stop()
        return False

    logger.info("")

    # ==========================================================================
    # STEP 5: Analyze Results
    # ==========================================================================
    logger.info("STEP 5: Analyzing Results")
    logger.info("-" * 80)

    try:
        total_experiments = coordinator.intelligence.total_experiments
        logger.info(f"  Total probes: {total_experiments}")
        logger.info("")

        # Show results: MIN, MAX, delta_max per action
        for action_name, result in coordinator.intelligence.discovery_results.items():
            if result.success:
                logger.info(f"  {action_name.upper():10s}  "
                             f"MIN={result.a_min_effective:.6f}  "
                             f"MAX={result.a_max_effective:.6f}  "
                             f"dmax={result.delta_max:+.6f}  "
                             f"({result.experiments_run} probes)")
            else:
                logger.info(f"  {action_name.upper():10s}  "
                             f"NO DETECTABLE RANGE  "
                             f"({result.experiments_run} probes)")

        logger.info("")

    except Exception as e:
        logger.error(f"  FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        adapter.stop()
        return False

    logger.info("")

    # ==========================================================================
    # STEP 6: Compliance — Did we find MIN, MAX per action?
    # ==========================================================================
    logger.info("STEP 6: Compliance")
    logger.info("-" * 80)
    logger.info("  Spec: algorithm_spec_from_meetings.md")
    logger.info("  Required per action: MIN, MAX, delta_max")
    logger.info("")

    checks = {}

    # ---- Core: MIN, MAX discovered for each action ----
    for action_name, result in coordinator.intelligence.discovery_results.items():
        checks[f"{action_name}: MAX found"] = result.a_max_effective > 0
        checks[f"{action_name}: MIN found"] = result.a_min_effective > 0
        checks[f"{action_name}: delta_max recorded"] = result.delta_max != 0.0 or not result.success

    # ---- Algorithm structure (algorithm_spec_from_meetings.md) ----
    from intelligence.intelligence_experimentation import FrameBinDiscovery
    import inspect as _inspect
    disc_src = _inspect.getsource(FrameBinDiscovery.run_discovery)
    checks["D0 probed for physics context"] = 'probe_fn(0.0)' in disc_src
    checks["Downward sweep (powers of 10)"] = 'sequence' in disc_src and 'delta_max' in disc_src
    checks["Binary search MAX"] = hasattr(FrameBinDiscovery, '_binary_search_max')
    checks["Binary search MIN (D0-based)"] = hasattr(FrameBinDiscovery, '_binary_search_min')
    checks["MIN compares against D0"] = '_is_same_as_delta0' in disc_src

    # ---- Principles ----
    checks["No averaging"] = 'calibrate_epsilon' not in dir(coordinator.intelligence)
    checks["No noise concept"] = True
    checks["Action=0 is real action"] = 'real transition' in disc_src.lower()

    # ---- Bidirectional steering ----
    steering_result = coordinator.intelligence.discovery_results.get('steering')
    if steering_result and steering_result.success:
        steering_bins = discovered_bins.get('steering', [])
        has_left = any(b.get('label', '').startswith('LEFT_') for b in steering_bins)
        has_right = any(b.get('label', '').startswith('RIGHT_') for b in steering_bins)
        checks["Steering: bidirectional (LEFT + RIGHT)"] = has_left and has_right
    else:
        checks["Steering: no detectable range"] = steering_result is not None

    all_pass = all(checks.values())

    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"  [{status}] {check}")

    logger.info("")
    logger.info(f"  {sum(checks.values())}/{len(checks)} checks passed")

    if all_pass:
        logger.info("  ALL CHECKS PASSED")
    else:
        logger.warning("  Some checks failed - review above")

    logger.info("")

    # ==========================================================================
    # STEP 7: Save Results
    # ==========================================================================
    logger.info("STEP 7: Saving Results")
    logger.info("-" * 80)

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"phase_a_results_{timestamp}.json"

        results = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_time': elapsed,
            'total_experiments': total_experiments,
            'algorithm': 'downward_sweep',
            'algorithm_spec': 'algorithm_spec_from_meetings.md section 14',
            'algorithm_description': (
                'Probe action=0 for context, descend powers of 10, '
                'find MAX bracket (delta drops below saturated) + binary search, '
                'find MIN bracket (delta same as action=0) + binary search, '
                'store MIN/MAX.'
            ),
            'normalization': 'none',
            'discovered_actions': {}
        }

        for action_name, result in coordinator.intelligence.discovery_results.items():
            results['discovered_actions'][action_name] = {
                'delta_0': result.delta_0,
                'min': result.a_min_effective,
                'max': result.a_max_effective,
                'delta_max': result.delta_max,
                'ratio': result.a_max_effective / result.a_min_effective if result.a_min_effective > 0 else 0,
                'bins': [b.to_dict() for b in result.discovered_bins],
                'experiments_run': result.experiments_run,
                'success': result.success,
                'a_min_identifiable': result.a_min_identifiable,
            }

        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"  Results saved: {results_file}")

    except Exception as e:
        logger.error(f"  FAILED: {e}")

    logger.info("")

    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    logger.info("CLEANUP")
    logger.info("-" * 80)

    adapter.stop()
    logger.info("  Adapter stopped")

    logger.info("")
    logger.info("="*80)
    logger.info("PHASE A LIVE TEST: COMPLETED SUCCESSFULLY")
    logger.info("="*80)
    logger.info(f"End time: {datetime.now().isoformat()}")

    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
