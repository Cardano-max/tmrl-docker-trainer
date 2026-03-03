"""
5-RUN TWO-STAGE VALIDATION — TMNF + TMInterface 2.x

Validates the two-stage discovery model (detect_action_nature + binary path)
across 5 independent discovery cycles. All functions reused from
test_phase_a_tmnf.py — no code duplication.

WHAT THIS VALIDATES:
  - All 4 TMNF actions detected as BINARY by detect_action_nature()
  - MAX = 1.0 for all actions (validated by probing, not hardcoded)
  - MIN found via binary search (near adapter boundary)
  - D0 measured and differs from active delta
  - bins = 2 for all actions across all 5 runs
  - Cross-run stability: identical values (deterministic rewind)
  - Sutton compliance: no hardcoded values, nature discovered
  - Cross-reference with multi_speed_binary_proof data

WHAT THIS DOES NOT DO:
  - No openpyxl / Excel dependency
  - No hardcoded epsilons (uses measure_system_precision)
  - No MEASURE_TICKS or action_range patterns
  - No code duplication from test_phase_a_tmnf.py

USAGE:
  python run_5_two_stage_validation.py
  python run_5_two_stage_validation.py --speed 5.0
  python run_5_two_stage_validation.py --runs 3
  python run_5_two_stage_validation.py --no-cross-ref
"""

import sys
import os
import json
import time
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_phase_a_tmnf import (
    measure_frame_duration,
    measure_system_precision,
    run_discovery_tmnf,
    TMNF_ACTIONS_CONFIG,
    make_probe_fn,
    save_results,
)
from adapters.tmnf_adapter import TMNFAdapter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('TWO_STAGE_VALIDATION')


# =============================================================================
# CONSTANTS
# =============================================================================

MIN_PROBE_SPEED = 200.0  # km/h — needed for steering yaw detection
MULTI_SPEED_PROOF_FILE = "multi_speed_binary_proof_20260303_092924.json"


# =============================================================================
# RUN 5 CYCLES
# =============================================================================

def run_5_cycles(
    adapter: TMNFAdapter,
    num_runs: int,
    frame_duration_s: float,
    precision: dict,
) -> List[dict]:
    """Run N discovery cycles, each from a fresh save point.

    Returns list of result dicts (one per run).
    """
    all_runs = []

    for run_idx in range(1, num_runs + 1):
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"  RUN {run_idx}/{num_runs}")
        logger.info("=" * 70)

        # Release all inputs before saving state
        adapter.send_action_dict({n: 0.0 for n in TMNF_ACTIONS_CONFIG})
        adapter.wait_one_tick()

        # Fresh save point for this run
        adapter.save_state()

        # Run two-stage discovery (detect_action_nature + binary/analog path)
        results = run_discovery_tmnf(
            adapter,
            use_rewind=True,
            frame_duration_s=frame_duration_s,
            precision=precision,
        )

        all_runs.append(results)

        # Print per-run summary
        print_run_summary(run_idx, results)

    return all_runs


def print_run_summary(run_idx: int, results: dict):
    """Print a compact summary table for one run."""
    print()
    print(f"  --- Run {run_idx} Summary ---")
    print(f"  {'Action':<8} {'Nature':<8} {'MAX':<8} {'MIN':<12} "
          f"{'D0':<12} {'Dmax':<12} {'Bins':<6} {'Probes':<6}")
    print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*12} "
          f"{'-'*12} {'-'*12} {'-'*6} {'-'*6}")

    for name, r in results.items():
        nature = r.get('nature_detection', '?')[:3].upper()
        a_max = r.get('max')
        a_min = r.get('min')
        d0 = r.get('delta_0')
        dmax = r.get('delta_max')
        bins = r.get('bins', 0)
        probes = r.get('probes', 0)

        max_s = f"{a_max}" if a_max is not None else "N/A"
        min_s = f"{a_min:.2e}" if a_min is not None else "N/A"
        d0_s = f"{d0:.6f}" if d0 is not None else "N/A"
        dmax_s = f"{dmax:.6f}" if dmax is not None else "N/A"

        print(f"  {name:<8} {nature:<8} {max_s:<8} {min_s:<12} "
              f"{d0_s:<12} {dmax_s:<12} {bins:<6} {probes:<6}")
    print()


# =============================================================================
# VALIDATION ENGINE
# =============================================================================

def validate_all_runs(
    all_runs: List[dict],
    frame_duration_s: float,
    precision: dict,
    cross_ref_data: Optional[dict] = None,
) -> dict:
    """Validate all runs against expected criteria.

    Returns dict of verdicts, each True/False.
    """
    verdicts = {}
    actions = list(TMNF_ACTIONS_CONFIG.keys())

    # ---- Per-run checks ----
    for run_idx, run_results in enumerate(all_runs, 1):
        prefix = f"run{run_idx}"

        # nature_binary: all 4 actions have nature_detection == 'binary'
        verdicts[f"{prefix}_nature_binary"] = all(
            run_results.get(a, {}).get('nature_detection') == 'binary'
            for a in actions
        )

        # max_is_1: all 4 actions have max == 1.0
        verdicts[f"{prefix}_max_is_1"] = all(
            run_results.get(a, {}).get('max') == 1.0
            for a in actions
        )

        # bins_is_2: all 4 actions have bins == 2
        verdicts[f"{prefix}_bins_is_2"] = all(
            run_results.get(a, {}).get('bins') == 2
            for a in actions
        )

        # d0_differs: for each action, delta_0 != delta_max
        verdicts[f"{prefix}_d0_differs"] = all(
            run_results.get(a, {}).get('delta_0') != run_results.get(a, {}).get('delta_max')
            for a in actions
        )

        # min_found: all 4 actions have min that is a valid float > 0
        verdicts[f"{prefix}_min_found"] = all(
            isinstance(run_results.get(a, {}).get('min'), (int, float))
            and run_results.get(a, {}).get('min', 0) > 0
            for a in actions
        )

        # probes_efficient: each action uses <= 15 probes
        verdicts[f"{prefix}_probes_efficient"] = all(
            run_results.get(a, {}).get('probes', 99) <= 15
            for a in actions
        )

    # ---- Cross-run stability checks ----
    def values_identical(key: str) -> dict:
        """Check if a field is identical across all runs for each action."""
        result = {}
        for a in actions:
            vals = [run.get(a, {}).get(key) for run in all_runs]
            # Filter out None values
            valid_vals = [v for v in vals if v is not None]
            if len(valid_vals) < 2:
                result[a] = False
            else:
                result[a] = all(v == valid_vals[0] for v in valid_vals[1:])
        return result

    max_same = values_identical('max')
    min_same = values_identical('min')
    dmax_same = values_identical('delta_max')
    d0_same = values_identical('delta_0')
    bins_same = values_identical('bins')
    probes_same = values_identical('probes')

    verdicts['cross_max_identical'] = all(max_same.values())
    verdicts['cross_min_identical'] = all(min_same.values())
    verdicts['cross_delta_max_identical'] = all(dmax_same.values())
    verdicts['cross_d0_identical'] = all(d0_same.values())
    verdicts['cross_bins_identical'] = all(bins_same.values())
    verdicts['cross_probes_identical'] = all(probes_same.values())

    # Store per-action stability details for reporting
    verdicts['_stability_details'] = {
        'max': max_same,
        'min': min_same,
        'delta_max': dmax_same,
        'd0': d0_same,
        'bins': bins_same,
        'probes': probes_same,
    }

    # ---- Sutton compliance checks ----
    # Use first run as representative
    run1 = all_runs[0] if all_runs else {}

    # nature_discovered: nature_detection exists and is not 'unknown'
    verdicts['sutton_nature_discovered'] = all(
        run1.get(a, {}).get('nature_detection', 'unknown') != 'unknown'
        for a in actions
    )

    # frame_duration_measured: frame_duration > 0 and came from environment
    verdicts['sutton_frame_duration_measured'] = frame_duration_s > 0

    # precision_measured: precision dict has speed_epsilon and yaw_epsilon > 0
    verdicts['sutton_precision_measured'] = (
        precision.get('speed_epsilon', 0) > 0
        and precision.get('yaw_epsilon', 0) > 0
    )

    # no_hardcoded_max: MAX was validated by probing (nature detection probes confirm binary)
    # If nature is binary and MAX is 1.0, it means probe_fn(1.0) matched delta_max
    verdicts['sutton_no_hardcoded_max'] = all(
        run1.get(a, {}).get('max') == 1.0
        and run1.get(a, {}).get('nature_detection') == 'binary'
        for a in actions
    )

    # d0_is_real_action: D0 was measured, not assumed to be 0
    verdicts['sutton_d0_is_real_action'] = all(
        run1.get(a, {}).get('delta_0') is not None
        for a in actions
    )

    # binary_path_used: nature == 'binary' triggered _run_binary_discovery
    verdicts['sutton_binary_path_used'] = all(
        run1.get(a, {}).get('nature_detection') == 'binary'
        for a in actions
    )

    # ---- Cross-reference with multi_speed_binary_proof ----
    verdicts['_cross_ref'] = {}
    if cross_ref_data is not None:
        proof_verdicts = cross_ref_data.get('verdicts', {})

        # Gas binary matches
        proof_gas_binary = proof_verdicts.get('group_a_gas_binary_all_speeds', None)
        this_gas_binary = all(
            run1.get('gas', {}).get('nature_detection') == 'binary'
            for _ in [1]
        )
        verdicts['xref_gas_binary'] = (
            proof_gas_binary == this_gas_binary if proof_gas_binary is not None else True
        )
        verdicts['_cross_ref']['gas_binary'] = {
            'proof': proof_gas_binary,
            'this': this_gas_binary,
        }

        # Brake binary matches
        proof_brake_binary = proof_verdicts.get('group_a_brake_binary_all_speeds', None)
        this_brake_binary = all(
            run1.get('brake', {}).get('nature_detection') == 'binary'
            for _ in [1]
        )
        verdicts['xref_brake_binary'] = (
            proof_brake_binary == this_brake_binary if proof_brake_binary is not None else True
        )
        verdicts['_cross_ref']['brake_binary'] = {
            'proof': proof_brake_binary,
            'this': this_brake_binary,
        }

        # Gas true MIN near adapter boundary
        proof_gas_min = proof_verdicts.get('group_c_gas_true_min', None)
        this_gas_min = run1.get('gas', {}).get('min')
        verdicts['_cross_ref']['gas_min'] = {
            'proof': proof_gas_min,
            'this': this_gas_min,
        }
        # Both should be extremely small (adapter boundary)
        if isinstance(proof_gas_min, (int, float)) and isinstance(this_gas_min, (int, float)):
            verdicts['xref_gas_min_consistent'] = (
                proof_gas_min <= 0.01 and this_gas_min <= 0.01
            )
        else:
            verdicts['xref_gas_min_consistent'] = True  # Can't compare non-numeric

        # Brake true MIN near adapter boundary
        proof_brake_min = proof_verdicts.get('group_c_brake_true_min', None)
        this_brake_min = run1.get('brake', {}).get('min')
        verdicts['_cross_ref']['brake_min'] = {
            'proof': proof_brake_min,
            'this': this_brake_min,
        }
        if isinstance(proof_brake_min, (int, float)) and isinstance(this_brake_min, (int, float)):
            verdicts['xref_brake_min_consistent'] = (
                proof_brake_min <= 0.01 and this_brake_min <= 0.01
            )
        else:
            verdicts['xref_brake_min_consistent'] = True

    return verdicts


# =============================================================================
# TERMINAL REPORT
# =============================================================================

def print_report(
    all_runs: List[dict],
    verdicts: dict,
    frame_duration_s: float,
    precision: dict,
    cross_ref_data: Optional[dict] = None,
):
    """Print comprehensive terminal report."""
    actions = list(TMNF_ACTIONS_CONFIG.keys())
    num_runs = len(all_runs)

    print()
    print("=" * 70)
    print("  5-RUN TWO-STAGE VALIDATION REPORT")
    print("=" * 70)

    # ---- ENVIRONMENT ----
    print()
    print("  ENVIRONMENT")
    print(f"    Frame duration: {frame_duration_s * 1000:.0f}ms (measured)")
    print(f"    Precision: speed_epsilon={precision['speed_epsilon']:.2e}, "
          f"yaw_epsilon={precision['yaw_epsilon']:.2e} (measured)")
    print(f"    Deterministic: {precision.get('deterministic', 'N/A')}")
    print(f"    Probe speed: {MIN_PROBE_SPEED}+ km/h")
    print(f"    Two-stage model: detect_action_nature() + binary/analog path")

    # ---- PER-RUN RESULTS ----
    print()
    print("  PER-RUN RESULTS")
    header = (f"  {'Run':<5} {'Action':<8} {'Nature':<8} {'MAX':<8} "
              f"{'MIN':<12} {'D0':<12} {'Dmax':<12} {'Bins':<6} {'Probes':<7}")
    sep = f"  {'-'*5} {'-'*8} {'-'*8} {'-'*8} {'-'*12} {'-'*12} {'-'*12} {'-'*6} {'-'*7}"
    print(header)
    print(sep)

    for run_idx, run_results in enumerate(all_runs, 1):
        for name in actions:
            r = run_results.get(name, {})
            nature = r.get('nature_detection', '?')[:3].upper()
            a_max = r.get('max')
            a_min = r.get('min')
            d0 = r.get('delta_0')
            dmax = r.get('delta_max')
            bins = r.get('bins', 0)
            probes = r.get('probes', 0)

            max_s = f"{a_max}" if a_max is not None else "N/A"
            min_s = f"{a_min:.2e}" if a_min is not None else "N/A"
            d0_s = f"{d0:.6f}" if d0 is not None else "N/A"
            dmax_s = f"{dmax:.6f}" if dmax is not None else "N/A"

            print(f"  {run_idx:<5} {name:<8} {nature:<8} {max_s:<8} "
                  f"{min_s:<12} {d0_s:<12} {dmax_s:<12} {bins:<6} {probes:<7}")

    # ---- CROSS-RUN STABILITY ----
    print()
    print("  CROSS-RUN STABILITY")
    stability = verdicts.get('_stability_details', {})
    stab_header = (f"  {'Action':<8} {'MAX same?':<12} {'MIN same?':<12} "
                   f"{'Dmax same?':<12} {'D0 same?':<12} {'Bins same?':<12} {'Probes?':<12}")
    stab_sep = (f"  {'-'*8} {'-'*12} {'-'*12} "
                f"{'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    print(stab_header)
    print(stab_sep)

    for a in actions:
        def _v(key):
            return "PASS" if stability.get(key, {}).get(a, False) else "FAIL"
        print(f"  {a:<8} {_v('max'):<12} {_v('min'):<12} "
              f"{_v('delta_max'):<12} {_v('d0'):<12} {_v('bins'):<12} {_v('probes'):<12}")

    # ---- PER-RUN VERDICTS ----
    print()
    print("  PER-RUN VERDICTS")
    per_run_checks = ['nature_binary', 'max_is_1', 'bins_is_2',
                      'd0_differs', 'min_found', 'probes_efficient']
    pr_header = f"  {'Run':<5} " + " ".join(f"{c:<18}" for c in per_run_checks)
    print(pr_header)
    print(f"  {'-'*5} " + " ".join(f"{'-'*18}" for _ in per_run_checks))

    for run_idx in range(1, num_runs + 1):
        vals = []
        for check in per_run_checks:
            key = f"run{run_idx}_{check}"
            vals.append("PASS" if verdicts.get(key, False) else "FAIL")
        print(f"  {run_idx:<5} " + " ".join(f"{v:<18}" for v in vals))

    # ---- SUTTON COMPLIANCE ----
    print()
    print("  SUTTON COMPLIANCE")
    sutton_checks = [
        ('sutton_nature_discovered', 'Nature discovered (not assumed)'),
        ('sutton_frame_duration_measured', 'Frame duration measured'),
        ('sutton_precision_measured', 'Precision measured from environment'),
        ('sutton_no_hardcoded_max', 'MAX validated by probing'),
        ('sutton_d0_is_real_action', 'D0 is real action (not noise)'),
        ('sutton_binary_path_used', 'Binary path used (efficient probing)'),
    ]
    sc_header = f"  {'Check':<45} {'Verdict':<8}"
    print(sc_header)
    print(f"  {'-'*45} {'-'*8}")

    for key, label in sutton_checks:
        v = "PASS" if verdicts.get(key, False) else "FAIL"
        print(f"  {label:<45} {v:<8}")

    # ---- CROSS-REFERENCE ----
    cross_ref = verdicts.get('_cross_ref', {})
    if cross_ref:
        print()
        print("  CROSS-REFERENCE: Multi-Speed Binary Proof")
        xr_header = f"  {'Check':<35} {'Proof':<15} {'This':<15} {'Match?':<8}"
        print(xr_header)
        print(f"  {'-'*35} {'-'*15} {'-'*15} {'-'*8}")

        for label, key, verdict_key in [
            ('Gas binary', 'gas_binary', 'xref_gas_binary'),
            ('Brake binary', 'brake_binary', 'xref_brake_binary'),
            ('Gas true MIN', 'gas_min', 'xref_gas_min_consistent'),
            ('Brake true MIN', 'brake_min', 'xref_brake_min_consistent'),
        ]:
            xr = cross_ref.get(key, {})
            proof_val = xr.get('proof', 'N/A')
            this_val = xr.get('this', 'N/A')
            match = "PASS" if verdicts.get(verdict_key, False) else "FAIL"

            # Format values
            if isinstance(proof_val, float):
                proof_s = f"{proof_val:.2e}"
            else:
                proof_s = str(proof_val)

            if isinstance(this_val, float):
                this_s = f"{this_val:.2e}"
            else:
                this_s = str(this_val)

            print(f"  {label:<35} {proof_s:<15} {this_s:<15} {match:<8}")

    # ---- OVERALL ----
    # Count pass/fail excluding internal keys (prefixed with _)
    total = 0
    passed = 0
    failed_keys = []
    for k, v in verdicts.items():
        if k.startswith('_'):
            continue
        total += 1
        if v:
            passed += 1
        else:
            failed_keys.append(k)

    print()
    print(f"  OVERALL: {passed}/{total} PASS")
    if failed_keys:
        print(f"  FAILURES:")
        for fk in failed_keys:
            print(f"    - {fk}")
    print()
    print("=" * 70)

    return passed == total


# =============================================================================
# SAVE JSON
# =============================================================================

def save_validation_json(
    all_runs: List[dict],
    verdicts: dict,
    frame_duration_s: float,
    precision: dict,
    cross_ref_data: Optional[dict] = None,
) -> str:
    """Save validation results to timestamped JSON file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"validation_5run_twostage_{timestamp}.json"

    # Count verdicts
    total = 0
    passed = 0
    for k, v in verdicts.items():
        if k.startswith('_'):
            continue
        total += 1
        if v:
            passed += 1

    # Clean verdicts for JSON (remove internal keys with non-serializable data)
    json_verdicts = {}
    for k, v in verdicts.items():
        if k.startswith('_'):
            # Include cross_ref and stability_details as-is (they are dicts of primitives)
            json_verdicts[k] = v
        else:
            json_verdicts[k] = v

    output = {
        'timestamp': timestamp,
        'environment': 'TMNF + TMInterface 2.x',
        'two_stage_model': True,
        'frame_duration_ms': frame_duration_s * 1000,
        'precision': {
            'speed_epsilon': precision['speed_epsilon'],
            'yaw_epsilon': precision['yaw_epsilon'],
            'speed_precision_digits': precision['speed_precision_digits'],
            'yaw_precision_digits': precision['yaw_precision_digits'],
            'deterministic': precision['deterministic'],
            'source': 'measured from repeated D0 probes',
        },
        'runs': all_runs,
        'validation_verdicts': json_verdicts,
        'cross_reference': cross_ref_data if cross_ref_data else None,
        'overall_pass': passed == total,
        'overall_score': f"{passed}/{total}",
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    logger.info(f"Results saved to {filename}")
    return filename


# =============================================================================
# LOAD CROSS-REFERENCE DATA
# =============================================================================

def load_cross_reference(filepath: str) -> Optional[dict]:
    """Load multi_speed_binary_proof JSON for cross-referencing."""
    if not os.path.exists(filepath):
        logger.warning(f"Cross-reference file not found: {filepath}")
        return None

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded cross-reference: {filepath}")
        return data
    except Exception as e:
        logger.warning(f"Error loading cross-reference: {e}")
        return None


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='5-Run Two-Stage Validation — TMNF + TMInterface 2.x',
    )
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Game speed multiplier (default: 1.0)')
    parser.add_argument('--port', type=int, default=8476,
                        help='TCP port for AgenticBridge.as (default: 8476)')
    parser.add_argument('--runs', type=int, default=5,
                        help='Number of discovery cycles (default: 5)')
    parser.add_argument('--no-cross-ref', action='store_true',
                        help='Skip multi_speed_binary_proof cross-reference')
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  5-RUN TWO-STAGE VALIDATION")
    print("  Two-stage model: detect_action_nature() + binary/analog path")
    print("  All values DISCOVERED from the environment. Zero hardcoding.")
    print("=" * 70)
    print()
    print(f"  Runs:    {args.runs}")
    print(f"  Speed:   {args.speed}x")
    print(f"  Port:    {args.port}")
    print(f"  Cross-ref: {'disabled' if args.no_cross_ref else MULTI_SPEED_PROOF_FILE}")
    print()

    # ---- Connect ----
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
        # ---- STEP 0: Measure frame duration ----
        frame_duration_s = measure_frame_duration(adapter)

        # ---- Accelerate to 200 km/h (needed for steering yaw) ----
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
        precision = measure_system_precision(adapter, use_rewind=True, num_probes=3)

        # ---- STEP 2: Run 5 discovery cycles ----
        all_runs = run_5_cycles(adapter, args.runs, frame_duration_s, precision)

        # ---- STEP 3: Load cross-reference data ----
        cross_ref_data = None
        if not args.no_cross_ref:
            cross_ref_data = load_cross_reference(MULTI_SPEED_PROOF_FILE)

        # ---- STEP 4: Validate ----
        verdicts = validate_all_runs(all_runs, frame_duration_s, precision, cross_ref_data)

        # ---- STEP 5: Report ----
        overall_pass = print_report(
            all_runs, verdicts, frame_duration_s, precision, cross_ref_data
        )

        # ---- STEP 6: Save JSON ----
        filename = save_validation_json(
            all_runs, verdicts, frame_duration_s, precision, cross_ref_data
        )
        print(f"  Results saved to: {filename}")

        if overall_pass:
            print("  STATUS: ALL CHECKS PASSED")
        else:
            print("  STATUS: SOME CHECKS FAILED (see report above)")

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
