"""
LIVE PRODUCTION TEST — SystemInitializer against actual TMNF game

Tests Phase 1 (System Initialization) INIT-01 through INIT-06 in production:

  TEST 1: Prior Knowledge Path (needs adapter for frame duration discovery)
    - SystemInitializer detects existing tmnf_phase_a_results_*.json on disk
    - Asks user if they want to use it (we simulate "y")
    - Loads bins, skips experimentation
    - Discovers frame duration from environment (INIT-06)
    - Prints status at each stage

  TEST 1b: Bad Config Rejection (no game needed)
    - Missing file, invalid JSON, missing required keys -> all fail

  TEST 2: Discovery Path (game needed — TMNF + TMInterface must be running)
    - SystemInitializer with empty results dir (no prior knowledge)
    - Connects to TMNF via TMNFAdapter on port 8476
    - Discovers frame duration from environment
    - Runs Sutton's downward sweep algorithm through ExperimentationCoordinator
    - Saves results, reports ready

SETUP (for Test 1 + Test 2):
  1. Launch TMNF via TMInterface 2.x
  2. Start a race (countdown finished)
  3. Run: python test_system_init_live.py --port 8476

USAGE:
  python test_system_init_live.py                     # Test 1b only (no game)
  python test_system_init_live.py --with-game         # All tests (game needed)
  python test_system_init_live.py --discovery-only    # Test 2 only
"""

import sys
import os
import json
import time
import argparse
import tempfile
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from control.system_initializer import SystemInitializer, InitializationResult


# =============================================================================
# RUBRICS
# =============================================================================

def rubric_check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    symbol = "[+]" if condition else "[X]"
    msg = f"  {symbol} {name}"
    if detail:
        msg += f": {detail}"
    print(msg)
    return condition


# =============================================================================
# TEST 1: PRIOR KNOWLEDGE PATH (needs game for frame duration discovery)
# =============================================================================

def test_prior_knowledge_path(port=8476):
    """
    INIT-02, INIT-04, INIT-05, INIT-06: System detects prior knowledge,
    asks user, loads bins, discovers frame duration from environment.
    """
    print("\n" + "=" * 60)
    print("TEST 1: PRIOR KNOWLEDGE PATH")
    print("  INIT-02: Detect prior knowledge")
    print("  INIT-04: User accepts, loads bins, skips experimentation")
    print("  INIT-05: Print status at each stage")
    print("  INIT-06: Frame duration DISCOVERED from environment")
    print("=" * 60)

    results = []

    # Simulate user saying "y" to prior knowledge
    init = SystemInitializer(
        config_path="config/tmnf_config.json",
        user_input_fn=lambda prompt: "y",
    )
    result = init.initialize()

    # INIT-01: Config validated
    results.append(rubric_check(
        "INIT-01: Config validated",
        str(result.stages.get('config_validation')) != 'InitializationStatus.FAILED',
        f"stage={result.stages.get('config_validation')}"
    ))

    # INIT-02: Prior knowledge detected
    results.append(rubric_check(
        "INIT-02: Prior knowledge detected",
        result.has_prior_knowledge,
        f"has_prior={result.has_prior_knowledge}"
    ))

    # INIT-04: Bins loaded from prior knowledge
    results.append(rubric_check(
        "INIT-04: Bins loaded",
        len(result.bins_acquired) > 0,
        f"actions={list(result.bins_acquired.keys())}"
    ))

    gas_bins = result.bins_acquired.get('gas', {}).get('bins', 0)
    steering_bins = result.bins_acquired.get('steering', {}).get('bins', 0)
    results.append(rubric_check(
        "INIT-04: Gas bins = 2 (binary)",
        gas_bins == 2,
        f"gas_bins={gas_bins}"
    ))
    results.append(rubric_check(
        "INIT-04: Steering bins > 2 (analog)",
        steering_bins > 2,
        f"steering_bins={steering_bins}"
    ))

    # INIT-04: Experimentation SKIPPED
    from control.system_initializer import InitializationStatus
    results.append(rubric_check(
        "INIT-04: Bin acquisition SKIPPED",
        result.stages.get('bin_acquisition') == InitializationStatus.SKIPPED,
        f"stage={result.stages.get('bin_acquisition')}"
    ))

    # INIT-06: Frame duration DISCOVERED (not from config)
    results.append(rubric_check(
        "INIT-06: Frame duration discovered from environment",
        result.frame_duration_ms > 0,
        f"frame_duration_ms={result.frame_duration_ms}"
    ))
    results.append(rubric_check(
        "INIT-06: Frame duration = 10ms (TMNF tick rate)",
        result.frame_duration_ms == 10.0,
        f"frame_duration_ms={result.frame_duration_ms}"
    ))
    results.append(rubric_check(
        "INIT-06: Frame duration discovery stage COMPLETED",
        result.stages.get('frame_duration_discovery') == InitializationStatus.COMPLETED,
        f"stage={result.stages.get('frame_duration_discovery')}"
    ))

    # INIT-05: Status printed
    results.append(rubric_check(
        "INIT-05: Status printed (visual above)",
        result.success,
        "Check console output for [~]/[+] status lines"
    ))

    # Overall
    results.append(rubric_check(
        "OVERALL: initialization succeeded",
        result.success,
        f"errors={result.errors}"
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n  Test 1 Result: {passed}/{total} rubrics passed")
    return passed == total


# =============================================================================
# TEST 1b: BAD CONFIG REJECTION (no game needed)
# =============================================================================

def test_bad_config_rejection():
    """INIT-01: System refuses to start with bad config."""
    print("\n" + "=" * 60)
    print("TEST 1b: BAD CONFIG REJECTION")
    print("  INIT-01: Refuse to start with bad config")
    print("=" * 60)

    results = []

    # Missing file
    init = SystemInitializer(config_path="nonexistent_config.json")
    r = init.initialize()
    results.append(rubric_check(
        "INIT-01: Missing file -> fail",
        not r.success,
        f"success={r.success}, errors={r.errors}"
    ))

    # Invalid JSON
    tmp = tempfile.mktemp(suffix=".json")
    with open(tmp, 'w') as f:
        f.write("this is not json {{{")
    init = SystemInitializer(config_path=tmp)
    r = init.initialize()
    results.append(rubric_check(
        "INIT-01: Invalid JSON -> fail",
        not r.success,
        f"success={r.success}"
    ))
    os.unlink(tmp)

    # Missing required keys (no actions)
    tmp = tempfile.mktemp(suffix=".json")
    bad_config = {"system_name": "test", "version": "1.0.0"}
    with open(tmp, 'w') as f:
        json.dump(bad_config, f)
    init = SystemInitializer(config_path=tmp)
    r = init.initialize()
    results.append(rubric_check(
        "INIT-01: Missing required keys -> fail",
        not r.success,
        f"success={r.success}"
    ))
    os.unlink(tmp)

    passed = sum(results)
    total = len(results)
    print(f"\n  Test 1b Result: {passed}/{total} rubrics passed")
    return passed == total


# =============================================================================
# TEST 1c: USER DECLINES PRIOR KNOWLEDGE (game needed)
# =============================================================================

def test_user_declines_prior(port=8476):
    """INIT-04: User says no to prior knowledge, system re-runs discovery."""
    print("\n" + "=" * 60)
    print("TEST 1c: USER DECLINES PRIOR KNOWLEDGE")
    print("  INIT-03: Re-run experimentation when user says no")
    print("  INIT-04: User has the choice")
    print("=" * 60)

    results = []

    # Simulate user saying "n" — re-run experimentation
    init = SystemInitializer(
        config_path="config/tmnf_config.json",
        user_input_fn=lambda prompt: "n",
    )
    result = init.initialize()

    results.append(rubric_check(
        "INIT-03: Discovery ran (user declined prior)",
        result.success,
        f"success={result.success}, errors={result.errors}"
    ))
    results.append(rubric_check(
        "INIT-04: has_prior_knowledge = False",
        not result.has_prior_knowledge,
        f"has_prior={result.has_prior_knowledge}"
    ))
    results.append(rubric_check(
        "Bins acquired via discovery",
        len(result.bins_acquired) > 0,
        f"actions={list(result.bins_acquired.keys())}"
    ))
    results.append(rubric_check(
        "INIT-06: Frame duration discovered",
        result.frame_duration_ms == 10.0,
        f"frame_duration_ms={result.frame_duration_ms}"
    ))

    passed = sum(results)
    total = len(results)
    print(f"\n  Test 1c Result: {passed}/{total} rubrics passed")
    return passed == total


# =============================================================================
# TEST 2: DISCOVERY PATH (requires game, no prior knowledge)
# =============================================================================

def test_discovery_path(port=8476):
    """INIT-03 + INIT-06: Full discovery from scratch, empty results dir."""
    print("\n" + "=" * 60)
    print("TEST 2: DISCOVERY PATH (LIVE)")
    print("  INIT-03: Auto bin discovery, no prior knowledge")
    print("  INIT-06: Frame duration discovered from environment")
    print(f"  Connecting to TMNF on port {port}...")
    print("=" * 60)

    results = []

    tmp_dir = tempfile.mkdtemp(prefix="init_test_")
    try:
        config = {
            "system_name": "Sutton_Intelligence_System",
            "version": "1.0.0",
            "actions": {
                "gas": {"type": "binary", "range": [0.0, 1.0]},
                "brake": {"type": "binary", "range": [0.0, 1.0]},
                "steering": {"type": "analog", "range": [-1.0, 1.0]}
            },
            "feedbacks": {
                "speed": {"description": "Vehicle speed", "unit": "km/h",
                          "interval_size": 5.0, "expected_range": [0.0, 500.0]}
            },
            "environment": {
                "type": "tmnf", "host": "127.0.0.1", "port": port,
            },
            "experimentation": {
                "enabled": True, "search_precision": 0.001,
                "min_probe_speed_kmh": 10.0, "use_rewind": True
            },
            "prior_knowledge": {
                "check_on_startup": True,
                "results_dir": tmp_dir,
                "results_pattern": "tmnf_phase_a_results_*.json"
            }
        }
        cfg_path = os.path.join(tmp_dir, "test_config.json")
        with open(cfg_path, 'w') as f:
            json.dump(config, f, indent=2)

        t0 = time.time()
        init = SystemInitializer(config_path=cfg_path)
        result = init.initialize()
        elapsed = time.time() - t0

        results.append(rubric_check(
            "INIT-03: Initialization completed",
            result.success,
            f"time={elapsed:.1f}s, errors={result.errors}"
        ))
        results.append(rubric_check(
            "INIT-03: No prior knowledge (fresh discovery)",
            not result.has_prior_knowledge,
        ))
        results.append(rubric_check(
            "INIT-03: Bins acquired",
            len(result.bins_acquired) > 0,
            f"actions={list(result.bins_acquired.keys())}"
        ))

        # INIT-06: Frame duration discovered
        results.append(rubric_check(
            "INIT-06: Frame duration discovered = 10ms",
            result.frame_duration_ms == 10.0,
            f"frame_duration_ms={result.frame_duration_ms}"
        ))

        if result.bins_acquired:
            gas = result.bins_acquired.get('gas', {})
            brake = result.bins_acquired.get('brake', {})
            steering = result.bins_acquired.get('steering', {})

            results.append(rubric_check("Gas = 2 bins",
                                        gas.get('bins', 0) == 2))
            results.append(rubric_check("Brake = 2 bins",
                                        brake.get('bins', 0) == 2))
            results.append(rubric_check("Steering > 2 bins",
                                        steering.get('bins', 0) > 2))

        # Check results saved
        import glob
        saved = glob.glob(os.path.join(tmp_dir, "tmnf_phase_a_results_*.json"))
        results.append(rubric_check(
            "Results saved to disk",
            len(saved) > 0,
            f"saved={len(saved)} files"
        ))

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    passed = sum(results)
    total = len(results)
    print(f"\n  Test 2 Result: {passed}/{total} rubrics passed")
    return passed == total


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Live SystemInitializer test")
    parser.add_argument("--with-game", action="store_true",
                        help="Run all tests (requires TMNF running)")
    parser.add_argument("--discovery-only", action="store_true",
                        help="Run only the discovery test")
    parser.add_argument("--port", type=int, default=8476,
                        help="TMInterface TCP port (default: 8476)")
    args = parser.parse_args()

    print("=" * 60)
    print("SYSTEM INITIALIZER — LIVE PRODUCTION TEST")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Config: config/tmnf_config.json")
    print(f"  Port: {args.port}")
    print("=" * 60)

    all_passed = True

    if not args.discovery_only:
        # Test 1b: Bad config rejection (no game)
        if not test_bad_config_rejection():
            all_passed = False

    if args.with_game or args.discovery_only:
        if not args.discovery_only:
            # Test 1: Prior knowledge path (game needed for frame duration)
            if not test_prior_knowledge_path(port=args.port):
                all_passed = False

            # Test 1c: User declines prior knowledge (game needed)
            if not test_user_declines_prior(port=args.port):
                all_passed = False

        # Test 2: Discovery path (game needed)
        if not test_discovery_path(port=args.port):
            all_passed = False
    else:
        print("\n  [o] Skipping live tests — use --with-game to enable")

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED — see details above")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
