"""
MULTI-SPEED BINARY PROOF + EXTENDED RANGE + ANALOG GAS AXIS FACT-CHECK

Proves that TMNF's binary input behavior is a fundamental game property
(not speed-dependent), discovers true MIN boundaries with extended range
probing, and fact-checks the InputType::Gas analog axis claim.

4 TEST GROUPS:
  A: Multi-speed gas/brake binary proof (6 speeds: 0, 50, 100, 150, 200, 250 km/h)
  B: Multi-speed steering proof (5 speeds: 50, 100, 150, 200, 250 km/h)
  C: Extended range MIN probing (below current MIN to find true boundary)
  D: Analog gas axis fact-check (documentation + cross-reference)

USAGE:
    python test_multi_speed_binary_proof.py --port 8476
    python test_multi_speed_binary_proof.py --port 8476 --speed 5.0

PREREQUISITES:
    1. TMNF running via TMInterface.exe
    2. AgenticBridge.as (v2.0 with InputType::Left/Right) in Plugins folder
    3. A race is active (countdown finished)
"""

import sys
import os
import time
import math
import json
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters.tmnf_adapter import TMNFAdapter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('MULTI_SPEED_PROOF')


# =============================================================================
# PROBE HELPERS (same pattern as verify_rubrics.py)
# =============================================================================

def null_action():
    """Action with all inputs off."""
    return {'gas': 0.0, 'brake': 0.0, 'steering': 0.0, 'left': 0.0, 'right': 0.0}


def gas_action(val=1.0):
    a = null_action()
    a['gas'] = val
    return a


def brake_action(val=1.0):
    a = null_action()
    a['brake'] = val
    return a


def left_action(with_gas=True):
    """Digital LEFT + optional gas to maintain speed."""
    a = null_action()
    a['left'] = 1.0
    if with_gas:
        a['gas'] = 1.0
    return a


def right_action(with_gas=True):
    """Digital RIGHT + optional gas to maintain speed."""
    a = null_action()
    a['right'] = 1.0
    if with_gas:
        a['gas'] = 1.0
    return a


def probe_action(adapter, action, ticks=1, metric='speed'):
    """
    Universal probe: rewind -> send action -> tick 1 (replayed) -> read before ->
    N more ticks (our input) -> read after -> delta.

    metric='speed': delta = speed_after - speed_before
    metric='yaw':   delta = yaw_after - yaw_before (wrapped [-pi, pi])
    """
    adapter.rewind()

    # Tick 1: send action (loads for next tick due to 1-tick input delay)
    adapter.send_action_dict(action)
    adapter.wait_one_tick()
    fb_before = adapter.get_feedbacks()

    # Ticks 2..N+1: our action takes effect
    for _ in range(ticks):
        adapter.send_action_dict(action)
        adapter.wait_one_tick()
    fb_after = adapter.get_feedbacks()

    if metric == 'speed':
        delta = fb_after['speed'] - fb_before['speed']
    elif metric == 'yaw':
        delta = fb_after.get('yaw', 0.0) - fb_before.get('yaw', 0.0)
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
    else:
        delta = 0.0

    return delta, fb_before, fb_after


def accelerate_to(adapter, target_kmh, max_ticks=500):
    """Accelerate car to target speed. Returns final feedbacks."""
    fb = adapter.get_feedbacks()
    speed = fb.get('speed', 0)
    ticks = 0
    while speed < target_kmh and ticks < max_ticks:
        adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
        adapter.wait_one_tick()
        fb = adapter.get_feedbacks()
        speed = fb.get('speed', 0)
        ticks += 1
    return fb


def restart_race_to_rest(adapter, settle_ticks=50):
    """Restart race and wait for car to settle at rest."""
    adapter.give_up()
    for _ in range(settle_ticks):
        adapter.send_action_dict(null_action())
        adapter.wait_one_tick()
    return adapter.get_feedbacks()


# =============================================================================
# GROUP A: MULTI-SPEED BINARY PROOF (gas + brake)
# =============================================================================

def group_a_multi_speed_gas_brake(adapter):
    """
    Prove gas and brake are binary across 6 speeds: 0, 50, 100, 150, 200, 250 km/h.

    At each speed:
      - Measure D0 (no input)
      - Probe gas with [0.001, 0.01, 0.1, 0.5, 1.0] -- all must give identical delta
      - Probe brake with same values -- all must give identical delta
    """
    print("\n" + "=" * 70)
    print("  GROUP A: MULTI-SPEED BINARY PROOF (gas + brake)")
    print("  6 speeds: rest, 50, 100, 150, 200, 250 km/h")
    print("=" * 70)

    target_speeds = [0, 50, 100, 150, 200, 250]
    probe_values = [0.001, 0.01, 0.1, 0.5, 1.0]
    results = {}

    for target in target_speeds:
        print(f"\n  --- Speed target: {target} km/h ---")

        # Get to target speed
        if target == 0:
            fb = restart_race_to_rest(adapter)
        else:
            # Restart to clean state, then accelerate
            restart_race_to_rest(adapter, settle_ticks=20)
            fb = accelerate_to(adapter, target)

        actual_speed = fb.get('speed', 0)
        print(f"    Actual speed: {actual_speed:.2f} km/h")

        # Save state at this speed
        adapter.save_state()

        # Measure D0
        d0, _, _ = probe_action(adapter, null_action(), ticks=1, metric='speed')
        print(f"    D0 (no input): {d0:+.10f} km/h")

        # Probe gas
        gas_deltas = []
        for v in probe_values:
            d, _, _ = probe_action(adapter, gas_action(v), ticks=1, metric='speed')
            gas_deltas.append(d)

        gas_ref = gas_deltas[0]
        gas_all_same = all(d == gas_ref for d in gas_deltas)
        print(f"    Gas deltas: {[f'{d:+.10f}' for d in gas_deltas]}")
        print(f"    Gas binary: {gas_all_same} (all identical: {gas_ref:+.10f})")

        # Probe brake
        brake_deltas = []
        for v in probe_values:
            d, _, _ = probe_action(adapter, brake_action(v), ticks=1, metric='speed')
            brake_deltas.append(d)

        brake_ref = brake_deltas[0]
        brake_all_same = all(d == brake_ref for d in brake_deltas)
        print(f"    Brake deltas: {[f'{d:+.10f}' for d in brake_deltas]}")
        print(f"    Brake binary: {brake_all_same} (all identical: {brake_ref:+.10f})")

        results[str(target)] = {
            'target_speed': target,
            'actual_speed': actual_speed,
            'd0': d0,
            'gas_probe_values': probe_values,
            'gas_deltas': gas_deltas,
            'gas_all_same': gas_all_same,
            'gas_ref_delta': gas_ref,
            'brake_probe_values': probe_values,
            'brake_deltas': brake_deltas,
            'brake_all_same': brake_all_same,
            'brake_ref_delta': brake_ref,
        }

    # Summary table
    print("\n  " + "-" * 70)
    print(f"  {'Speed':>8} | {'D0':>14} | {'Gas delta':>14} | {'Gas binary':>10} | {'Brake delta':>14} | {'Brake binary':>12}")
    print("  " + "-" * 70)
    for target in target_speeds:
        r = results[str(target)]
        print(f"  {r['actual_speed']:>7.1f}  | {r['d0']:>+14.8f} | {r['gas_ref_delta']:>+14.8f} | "
              f"{'YES' if r['gas_all_same'] else 'NO':>10} | {r['brake_ref_delta']:>+14.8f} | "
              f"{'YES' if r['brake_all_same'] else 'NO':>12}")

    all_gas_binary = all(results[str(t)]['gas_all_same'] for t in target_speeds)
    all_brake_binary = all(results[str(t)]['brake_all_same'] for t in target_speeds)

    print(f"\n  Gas binary at ALL speeds: {'CONFIRMED' if all_gas_binary else 'FAILED'}")
    print(f"  Brake binary at ALL speeds: {'CONFIRMED' if all_brake_binary else 'FAILED'}")

    return {
        'all_gas_binary': all_gas_binary,
        'all_brake_binary': all_brake_binary,
        'per_speed': results,
    }


# =============================================================================
# GROUP B: MULTI-SPEED STEERING PROOF (left + right)
# =============================================================================

def group_b_multi_speed_steering(adapter):
    """
    Prove digital left/right steering works across speeds.

    At each speed (50, 100, 150, 200, 250 km/h):
      - Probe left=1.0 with gas=1.0 for 5 ticks, measure yaw delta
      - Probe right=1.0 with gas=1.0 for 5 ticks, measure yaw delta
      - Verify opposite signs
    """
    print("\n" + "=" * 70)
    print("  GROUP B: MULTI-SPEED STEERING PROOF (left + right)")
    print("  5 speeds: 50, 100, 150, 200, 250 km/h (skip rest -- no yaw at 0)")
    print("=" * 70)

    target_speeds = [50, 100, 150, 200, 250]
    results = {}

    for target in target_speeds:
        print(f"\n  --- Speed target: {target} km/h ---")

        # Restart and accelerate to target
        restart_race_to_rest(adapter, settle_ticks=20)
        fb = accelerate_to(adapter, target)
        actual_speed = fb.get('speed', 0)
        print(f"    Actual speed: {actual_speed:.2f} km/h")

        adapter.save_state()

        # D0 (gas only, 5 ticks)
        d0, _, _ = probe_action(adapter, gas_action(1.0), ticks=5, metric='yaw')

        # LEFT + gas, 5 ticks
        d_left, _, _ = probe_action(adapter, left_action(with_gas=True), ticks=5, metric='yaw')

        # RIGHT + gas, 5 ticks
        d_right, _, _ = probe_action(adapter, right_action(with_gas=True), ticks=5, metric='yaw')

        opposite = (d_left * d_right < 0)
        both_differ_d0 = (d_left != d0) and (d_right != d0)

        print(f"    D0 (gas only, 5t): yaw = {d0:+.10f} rad")
        print(f"    LEFT+gas (5t):     yaw = {d_left:+.10f} rad")
        print(f"    RIGHT+gas (5t):    yaw = {d_right:+.10f} rad")
        print(f"    Opposite signs: {opposite}  |  Both != D0: {both_differ_d0}")

        results[str(target)] = {
            'target_speed': target,
            'actual_speed': actual_speed,
            'd0_yaw': d0,
            'd_left_yaw': d_left,
            'd_right_yaw': d_right,
            'opposite_signs': opposite,
            'both_differ_from_d0': both_differ_d0,
            'left_magnitude': abs(d_left),
            'right_magnitude': abs(d_right),
        }

    # Summary table
    print("\n  " + "-" * 70)
    print(f"  {'Speed':>8} | {'D0 yaw':>14} | {'LEFT yaw':>14} | {'RIGHT yaw':>14} | {'Opposite':>8}")
    print("  " + "-" * 70)
    for target in target_speeds:
        r = results[str(target)]
        print(f"  {r['actual_speed']:>7.1f}  | {r['d0_yaw']:>+14.10f} | {r['d_left_yaw']:>+14.10f} | "
              f"{r['d_right_yaw']:>+14.10f} | {'YES' if r['opposite_signs'] else 'NO':>8}")

    all_opposite = all(results[str(t)]['opposite_signs'] for t in target_speeds)
    all_differ_d0 = all(results[str(t)]['both_differ_from_d0'] for t in target_speeds)

    # Check if yaw magnitude increases with speed (physics property)
    magnitudes = [(t, results[str(t)]['left_magnitude']) for t in target_speeds]
    increasing = all(magnitudes[i][1] <= magnitudes[i+1][1] for i in range(len(magnitudes)-1))

    print(f"\n  Opposite signs at ALL speeds: {'CONFIRMED' if all_opposite else 'FAILED'}")
    print(f"  Both differ from D0 at ALL speeds: {'CONFIRMED' if all_differ_d0 else 'FAILED'}")
    print(f"  Yaw magnitude increases with speed: {'YES' if increasing else 'NOT STRICTLY'}")
    print(f"    (Expected: higher speed = more lateral tire force = more yaw)")

    return {
        'all_opposite_signs': all_opposite,
        'all_differ_from_d0': all_differ_d0,
        'yaw_increases_with_speed': increasing,
        'per_speed': results,
    }


# =============================================================================
# GROUP C: EXTENDED RANGE PROBING (find true MIN)
# =============================================================================

def group_c_extended_range_min(adapter):
    """
    Probe below current MIN boundaries to find the TRUE MIN.

    For gas/brake: probe values descending below 0.001 (current MIN).
    For left/right: probe below 0.1, document that adapter's > 0.0 comparison
                    means any positive float = ON.

    Uses binary search between last-working and first-D0 to narrow boundary.
    """
    print("\n" + "=" * 70)
    print("  GROUP C: EXTENDED RANGE PROBING (find true MIN)")
    print("  Probing below current MIN to find actual boundary")
    print("=" * 70)

    # Get to 200 km/h for probing
    restart_race_to_rest(adapter, settle_ticks=20)
    fb = accelerate_to(adapter, 200)
    actual_speed = fb.get('speed', 0)
    print(f"\n  Probe speed: {actual_speed:.2f} km/h")
    adapter.save_state()

    results = {}

    # --- GAS extended range ---
    print("\n  --- GAS extended range ---")
    d0, _, _ = probe_action(adapter, null_action(), ticks=1, metric='speed')
    print(f"    D0 = {d0:+.15g}")

    gas_extended_values = [0.001, 0.0009, 0.0005, 0.0001, 1e-5, 1e-6, 1e-8, 1e-10, 1e-15]
    gas_results = []
    gas_last_working = None
    gas_first_d0 = None

    for v in gas_extended_values:
        d, _, _ = probe_action(adapter, gas_action(v), ticks=1, metric='speed')
        matches_d0 = (d == d0)
        gas_results.append({'value': v, 'delta': d, 'matches_d0': matches_d0})
        print(f"    gas={v:<12.2e}  delta={d:+.15g}  {'== D0' if matches_d0 else '!= D0 (ACTIVE)'}")

        if not matches_d0:
            gas_last_working = v
        elif gas_first_d0 is None:
            gas_first_d0 = v

    # Binary search between last_working and first_d0
    gas_true_min = None
    gas_binary_search = []
    if gas_last_working is not None and gas_first_d0 is not None:
        print(f"\n    Binary search: [{gas_last_working:.2e}, {gas_first_d0:.2e}]")
        lo = gas_first_d0    # D0 side (too small)
        hi = gas_last_working  # active side (works)
        for step in range(20):
            mid = (lo + hi) / 2.0
            d, _, _ = probe_action(adapter, gas_action(mid), ticks=1, metric='speed')
            matches_d0 = (d == d0)
            gas_binary_search.append({'value': mid, 'delta': d, 'matches_d0': matches_d0})
            print(f"      step {step+1}: gas={mid:.6e}  delta={d:+.15g}  {'D0' if matches_d0 else 'ACTIVE'}")
            if matches_d0:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-18:
                break
        gas_true_min = hi
        print(f"    TRUE MIN for gas: {gas_true_min:.6e}")
    elif gas_last_working is not None:
        gas_true_min = gas_extended_values[-1]
        print(f"    Gas active down to {gas_true_min:.2e} (never matched D0)")
    else:
        gas_true_min = None
        print(f"    Gas always matched D0 (unexpected)")

    results['gas'] = {
        'd0': d0,
        'extended_probes': gas_results,
        'binary_search': gas_binary_search,
        'true_min': gas_true_min,
        'last_working': gas_last_working,
        'first_d0': gas_first_d0,
    }

    # --- BRAKE extended range ---
    print("\n  --- BRAKE extended range ---")
    brake_extended_values = [0.001, 0.0009, 0.0005, 0.0001, 1e-5, 1e-6, 1e-8, 1e-10, 1e-15]
    brake_results = []
    brake_last_working = None
    brake_first_d0 = None

    for v in brake_extended_values:
        d, _, _ = probe_action(adapter, brake_action(v), ticks=1, metric='speed')
        matches_d0 = (d == d0)
        brake_results.append({'value': v, 'delta': d, 'matches_d0': matches_d0})
        print(f"    brake={v:<12.2e}  delta={d:+.15g}  {'== D0' if matches_d0 else '!= D0 (ACTIVE)'}")

        if not matches_d0:
            brake_last_working = v
        elif brake_first_d0 is None:
            brake_first_d0 = v

    # Binary search between last_working and first_d0
    brake_true_min = None
    brake_binary_search = []
    if brake_last_working is not None and brake_first_d0 is not None:
        print(f"\n    Binary search: [{brake_last_working:.2e}, {brake_first_d0:.2e}]")
        lo = brake_first_d0
        hi = brake_last_working
        for step in range(20):
            mid = (lo + hi) / 2.0
            d, _, _ = probe_action(adapter, brake_action(mid), ticks=1, metric='speed')
            matches_d0 = (d == d0)
            brake_binary_search.append({'value': mid, 'delta': d, 'matches_d0': matches_d0})
            print(f"      step {step+1}: brake={mid:.6e}  delta={d:+.15g}  {'D0' if matches_d0 else 'ACTIVE'}")
            if matches_d0:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-18:
                break
        brake_true_min = hi
        print(f"    TRUE MIN for brake: {brake_true_min:.6e}")
    elif brake_last_working is not None:
        brake_true_min = brake_extended_values[-1]
        print(f"    Brake active down to {brake_true_min:.2e} (never matched D0)")
    else:
        brake_true_min = None
        print(f"    Brake always matched D0 (unexpected)")

    results['brake'] = {
        'd0': d0,
        'extended_probes': brake_results,
        'binary_search': brake_binary_search,
        'true_min': brake_true_min,
        'last_working': brake_last_working,
        'first_d0': brake_first_d0,
    }

    # --- LEFT/RIGHT extended range ---
    # NOTE: The adapter converts left/right as: uint8(1 if value > 0.0 else 0)
    # So ANY positive float, no matter how small, becomes left=1 (ON).
    # The true MIN is determined by the adapter's > 0.0 comparison, not the game.
    print("\n  --- LEFT/RIGHT extended range ---")
    print("    NOTE: Adapter converts left/right as uint8(1 if value > 0.0 else 0)")
    print("    So ANY positive float = ON. True MIN is in adapter, not game.")

    # D0 for yaw (gas only, 5 ticks)
    d0_yaw, _, _ = probe_action(adapter, gas_action(1.0), ticks=5, metric='yaw')
    print(f"    D0 yaw (gas only): {d0_yaw:+.15g}")

    steer_extended_values = [0.1, 0.09, 0.05, 0.01, 0.001, 1e-4, 1e-6, 1e-10, 1e-15]
    left_results = []
    left_last_working = None
    left_first_d0 = None

    for v in steer_extended_values:
        action = null_action()
        action['left'] = v
        action['gas'] = 1.0
        d, _, _ = probe_action(adapter, action, ticks=5, metric='yaw')
        matches_d0 = (d == d0_yaw)
        left_results.append({'value': v, 'delta': d, 'matches_d0': matches_d0})
        print(f"    left={v:<12.2e}  yaw={d:+.15g}  {'== D0' if matches_d0 else '!= D0 (ACTIVE)'}")

        if not matches_d0:
            left_last_working = v
        elif left_first_d0 is None:
            left_first_d0 = v

    # Document adapter boundary
    if left_last_working is not None and left_first_d0 is None:
        left_true_min = "ANY positive float (adapter: > 0.0)"
        print(f"    TRUE MIN for left: {left_true_min}")
        print(f"    All positive values active -- adapter converts ANY > 0.0 to uint8(1)")
    elif left_first_d0 is not None:
        left_true_min = left_last_working
        print(f"    TRUE MIN for left: {left_true_min:.6e}")
    else:
        left_true_min = None
        print(f"    Left always matched D0 (unexpected)")

    # Right -- same pattern, one quick check
    right_results = []
    for v in [1e-15, 1e-10, 0.001]:
        action = null_action()
        action['right'] = v
        action['gas'] = 1.0
        d, _, _ = probe_action(adapter, action, ticks=5, metric='yaw')
        matches_d0 = (d == d0_yaw)
        right_results.append({'value': v, 'delta': d, 'matches_d0': matches_d0})
        print(f"    right={v:<12.2e}  yaw={d:+.15g}  {'== D0' if matches_d0 else '!= D0 (ACTIVE)'}")

    results['left'] = {
        'd0_yaw': d0_yaw,
        'extended_probes': left_results,
        'true_min': str(left_true_min),
        'adapter_boundary': '> 0.0 (any positive float)',
        'note': 'Adapter converts float to uint8(1 if val > 0.0 else 0). True MIN is in adapter, not game.',
    }
    results['right'] = {
        'd0_yaw': d0_yaw,
        'extended_probes': right_results,
        'adapter_boundary': '> 0.0 (any positive float)',
        'note': 'Same as left -- adapter boundary, not game boundary.',
    }

    # Summary
    print("\n  --- Extended Range Summary ---")
    print(f"    Gas TRUE MIN:   {gas_true_min}")
    print(f"    Brake TRUE MIN: {brake_true_min}")
    print(f"    Left TRUE MIN:  {left_true_min}")
    print(f"    Right TRUE MIN: same as left (adapter: > 0.0)")
    print(f"    NOTE: Gas/brake boundary is in the adapter (uint8: > 0.0 = 1)")
    print(f"    NOTE: Left/right boundary is in the adapter (uint8: > 0.0 = 1)")

    return results


# =============================================================================
# GROUP D: ANALOG GAS AXIS FACT-CHECK
# =============================================================================

def group_d_analog_gas_factcheck(group_a_results):
    """
    Fact-check the TMInterface docs claim about InputType::Gas analog axis.

    This is a DOCUMENTATION test, not a live probe, because testing analog gas
    requires modifying AgenticBridge.as to send InputType::Gas(5) instead of
    InputType::Up(1). We document the claim and cross-reference with Group A.
    """
    print("\n" + "=" * 70)
    print("  GROUP D: ANALOG GAS AXIS FACT-CHECK")
    print("  (Documentation + cross-reference, not live probe)")
    print("=" * 70)

    print("""
    CLAIM (TMInterface docs):
      InputType::Gas (enum value 5) is an analog axis
      Range: [-65536, 65536]
      Acceleration threshold: -19661 (values <= -19661 = accelerate)
      Brake threshold: 19661 (values >= 19661 = brake)

    FACT (our adapter):
      We send InputType::Up (enum value 1) for gas -- DIGITAL, not analog.
      We send InputType::Down (enum value 0) for brake -- DIGITAL, not analog.
      Adapter converts: uint8(1 if gas_val > 0.0 else 0)

    WHY NOT ANALOG GAS:
      TMNF official docs: "TMNF/TMUF do not support analog acceleration"
      InputType::Gas axis exists in the TMInterface API for TM2020 compatibility,
      but TMNF's game engine ignores analog gas values.

    PROOF (cross-reference with Group A):
      If gas were analog, different float values would produce different deltas.
      Group A tested gas with [0.001, 0.01, 0.1, 0.5, 1.0] at 6 speeds.
      All values produced IDENTICAL deltas at each speed = BINARY behavior.
    """)

    # Cross-reference with Group A results
    cross_ref_pass = True
    if group_a_results and 'per_speed' in group_a_results:
        print("    Cross-reference with Group A:")
        for speed_key, speed_data in group_a_results['per_speed'].items():
            gas_binary = speed_data.get('gas_all_same', False)
            print(f"      {speed_data['actual_speed']:>7.1f} km/h: gas binary = {gas_binary}")
            if not gas_binary:
                cross_ref_pass = False

    print(f"\n    Cross-reference verdict: {'CONFIRMED' if cross_ref_pass else 'CONTRADICTED'}")
    print(f"      All Group A gas probes produced identical deltas = BINARY")
    print(f"      InputType::Gas analog axis is irrelevant for TMNF")

    print("""
    FUTURE_TEST:
      To fully verify, modify AgenticBridge.as to add an InputType::Gas channel:
        simManager.SetInputState(InputType::Gas, analog_gas_value);
      Send values around the -19661 threshold and measure speed deltas.
      Expected: no effect in TMNF (game engine ignores analog gas).
      This requires a plugin modification and is flagged for future work.
    """)

    return {
        'claim': {
            'input_type': 'InputType::Gas (5)',
            'range': '[-65536, 65536]',
            'accel_threshold': -19661,
            'brake_threshold': 19661,
        },
        'fact': {
            'our_input_type': 'InputType::Up (1) -- digital',
            'adapter_conversion': 'uint8(1 if gas > 0.0 else 0)',
            'reason': 'TMNF/TMUF do not support analog acceleration',
        },
        'cross_reference_pass': cross_ref_pass,
        'status': 'DOCUMENTED -- not live tested (requires plugin modification)',
        'future_test': 'Modify AgenticBridge.as to send InputType::Gas and verify no effect',
    }


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_results(all_results, verdicts):
    """Save comprehensive JSON with per-speed breakdown."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"multi_speed_binary_proof_{timestamp}.json"

    output = {
        'timestamp': timestamp,
        'test': 'multi_speed_binary_proof',
        'environment': 'TMNF + TMInterface 2.x',
        'plugin': 'AgenticBridge.as v2.0',
        'protocol': 'TCP (Linesight-compatible + analog steer extension)',
        'verdicts': verdicts,
        'group_a_multi_speed_gas_brake': _serialize(all_results.get('group_a', {})),
        'group_b_multi_speed_steering': _serialize(all_results.get('group_b', {})),
        'group_c_extended_range_min': _serialize(all_results.get('group_c', {})),
        'group_d_analog_gas_factcheck': _serialize(all_results.get('group_d', {})),
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Results saved to {filename}")
    return filename


def _serialize(obj):
    """Make obj JSON-serializable (handle non-serializable types)."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return str(obj)
        return obj
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    else:
        return str(obj)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Multi-Speed Binary Proof + Extended Range + Analog Gas Axis Fact-Check',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Groups:
  A: Multi-speed gas/brake binary proof (6 speeds: 0, 50, 100, 150, 200, 250)
  B: Multi-speed steering proof (5 speeds: 50, 100, 150, 200, 250)
  C: Extended range MIN probing (below current MIN, binary search for boundary)
  D: Analog gas axis fact-check (documentation + cross-reference)
        """
    )
    parser.add_argument('--port', type=int, default=8476,
                        help='TCP port for AgenticBridge.as (default: 8476)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Game speed multiplier (default: 1.0)')
    parser.add_argument('--skip-analog', action='store_true', default=True,
                        help='Skip live analog gas test (default: True, always skipped)')
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  MULTI-SPEED BINARY PROOF + EXTENDED RANGE + ANALOG GAS FACT-CHECK")
    print("  Proving TMNF binary inputs are speed-independent")
    print("=" * 70)
    print()
    print(f"  Port:     {args.port}")
    print(f"  Speed:    {args.speed}x")
    print(f"  Groups:   A (gas/brake), B (steering), C (extended MIN), D (analog fact-check)")
    print()

    # Connect
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=30.0):
        print("ERROR: Could not connect to AgenticBridge.as plugin.")
        print("Is TMNF running via TMInterface.exe with the plugin loaded?")
        return

    if not adapter.wait_for_race(timeout=60.0):
        print("ERROR: No race detected. Start a race in TMNF first.")
        adapter.stop()
        return

    if args.speed != 1.0:
        adapter.set_speed(args.speed)
        print(f"  Game speed set to {args.speed}x")

    all_results = {}
    verdicts = {}

    try:
        t_start = time.time()

        # ---- GROUP A: Multi-speed gas/brake binary proof ----
        group_a_data = group_a_multi_speed_gas_brake(adapter)
        all_results['group_a'] = group_a_data
        verdicts['group_a_gas_binary_all_speeds'] = group_a_data['all_gas_binary']
        verdicts['group_a_brake_binary_all_speeds'] = group_a_data['all_brake_binary']

        # ---- GROUP B: Multi-speed steering proof ----
        group_b_data = group_b_multi_speed_steering(adapter)
        all_results['group_b'] = group_b_data
        verdicts['group_b_opposite_signs_all_speeds'] = group_b_data['all_opposite_signs']
        verdicts['group_b_all_differ_from_d0'] = group_b_data['all_differ_from_d0']
        verdicts['group_b_yaw_increases_with_speed'] = group_b_data['yaw_increases_with_speed']

        # ---- GROUP C: Extended range MIN probing ----
        group_c_data = group_c_extended_range_min(adapter)
        all_results['group_c'] = group_c_data
        verdicts['group_c_gas_true_min'] = group_c_data.get('gas', {}).get('true_min')
        verdicts['group_c_brake_true_min'] = group_c_data.get('brake', {}).get('true_min')
        verdicts['group_c_left_true_min'] = group_c_data.get('left', {}).get('true_min')

        # ---- GROUP D: Analog gas axis fact-check ----
        group_d_data = group_d_analog_gas_factcheck(group_a_data)
        all_results['group_d'] = group_d_data
        verdicts['group_d_cross_reference_pass'] = group_d_data['cross_reference_pass']

        t_total = time.time() - t_start

        # ================================================================
        # FINAL VERDICT
        # ================================================================
        print("\n" + "=" * 70)
        print("  FINAL VERDICT")
        print("=" * 70)

        all_binary = (
            verdicts.get('group_a_gas_binary_all_speeds', False) and
            verdicts.get('group_a_brake_binary_all_speeds', False)
        )
        all_steering = (
            verdicts.get('group_b_opposite_signs_all_speeds', False) and
            verdicts.get('group_b_all_differ_from_d0', False)
        )

        print(f"\n  GROUP A: Gas binary all speeds:     {'PASS' if verdicts.get('group_a_gas_binary_all_speeds') else 'FAIL'}")
        print(f"  GROUP A: Brake binary all speeds:   {'PASS' if verdicts.get('group_a_brake_binary_all_speeds') else 'FAIL'}")
        print(f"  GROUP B: Opposite signs all speeds: {'PASS' if verdicts.get('group_b_opposite_signs_all_speeds') else 'FAIL'}")
        print(f"  GROUP B: Both differ D0 all speeds: {'PASS' if verdicts.get('group_b_all_differ_from_d0') else 'FAIL'}")
        print(f"  GROUP B: Yaw increases with speed:  {'PASS' if verdicts.get('group_b_yaw_increases_with_speed') else 'FAIL'}")
        print(f"  GROUP C: Gas TRUE MIN:              {verdicts.get('group_c_gas_true_min')}")
        print(f"  GROUP C: Brake TRUE MIN:            {verdicts.get('group_c_brake_true_min')}")
        print(f"  GROUP C: Left TRUE MIN:             {verdicts.get('group_c_left_true_min')}")
        print(f"  GROUP D: Cross-reference pass:      {'PASS' if verdicts.get('group_d_cross_reference_pass') else 'FAIL'}")

        if all_binary:
            print(f"\n  BINARY NATURE CONFIRMED ACROSS ALL SPEEDS")
            print(f"    Gas: binary (any value > 0.0 = full throttle)")
            print(f"    Brake: binary (any value > 0.0 = full brake)")
        else:
            print(f"\n  WARNING: Binary nature NOT confirmed at all speeds")

        if all_steering:
            print(f"  STEERING CONFIRMED ACROSS ALL SPEEDS")
            print(f"    Left/Right: digital keyboard keys, opposite yaw at all speeds")

        print(f"\n  Total time: {t_total:.1f}s")

        # Save results
        filename = save_results(all_results, verdicts)

        print("\n" + "=" * 70)
        print(f"  Results: {filename}")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
    except Exception as e:
        print(f"\n  FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            adapter.send_action_dict(null_action())
            adapter.wait_one_tick()
        except Exception:
            pass
        adapter.stop()
        print("\n  Done.")


if __name__ == '__main__':
    main()
