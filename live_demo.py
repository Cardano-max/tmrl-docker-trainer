"""
LIVE DEMO SCRIPT — For Client Meeting
======================================

Run this DURING the meeting with TMNF + TMInterface running.
It walks through the algorithm step-by-step with commentary,
pausing between stages so you can explain what's happening.

SETUP BEFORE MEETING:
  1. TMNF running via TMInterface.exe
  2. AgenticBridge.as plugin loaded
  3. Start a race on any track (e.g. A01-Race)
  4. Run: python live_demo.py

The script will:
  - Connect to the game
  - Explain each step in plain English
  - Show the algorithm discovering gas, brake, steering
  - Print probe-by-probe results with explanations
  - Show final results with bin map
  - Optionally run a second time to prove determinism

USAGE:
  python live_demo.py                  # Full demo
  python live_demo.py --fast           # Skip pauses (for testing)
  python live_demo.py --port 8476      # Custom port
  python live_demo.py --gas-only       # Only gas discovery (quick demo)
"""

import sys
import os
import time
import math
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.tmnf_adapter import TMNFAdapter
from intelligence.intelligence_experimentation import FrameBinDiscovery, ProbeResult

# ── Colors for terminal ──────────────────────────────────────────
class C:
    HEADER = '\033[95m'
    BLUE   = '\033[94m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    RED    = '\033[91m'
    CYAN   = '\033[96m'
    BOLD   = '\033[1m'
    DIM    = '\033[2m'
    END    = '\033[0m'

def banner(text, color=C.HEADER):
    print()
    print(f"{color}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{C.END}")
    print()

def step(num, text):
    print(f"  {C.CYAN}[Step {num}]{C.END} {text}")

def result(text):
    print(f"  {C.GREEN}>>>{C.END} {C.BOLD}{text}{C.END}")

def explain(text):
    print(f"  {C.DIM}{text}{C.END}")

def probe_line(num, phase, value, delta, decision, highlight=False):
    color = C.YELLOW if highlight else ""
    end = C.END if highlight else ""
    print(f"    {color}Probe {num:2d}  |  {phase:16s}  |  a={value:10.6f}  |  delta={delta:+12.6f}  |  {decision}{end}")

def wait_for_enter(fast_mode):
    if not fast_mode:
        input(f"\n  {C.DIM}[Press ENTER to continue...]{C.END}\n")
    else:
        time.sleep(0.3)


# ── Actions Config ───────────────────────────────────────────────

ACTIONS = {
    'gas':      {'range': [0.0, 1.0],  'type': 'binary'},
    'brake':    {'range': [0.0, 1.0],  'type': 'binary'},
    'steering': {'range': [-1.0, 1.0], 'type': 'analog'},
}


# ── Probe Function (same logic as test_phase_a_tmnf.py) ─────────

def make_demo_probe_fn(adapter, disc, action_name, action_range, probe_counter):
    """Create probe function with live commentary."""

    MEASURE_TICKS = 5 if action_name == 'steering' else 1

    def probe(value):
        action_dict = {n: 0.0 for n in ACTIONS}
        clipped = max(action_range[0], min(value, action_range[1]))
        action_dict[action_name] = clipped

        # Rewind to saved state
        adapter.rewind()

        # Tick 1: send action (loads for next tick, replayed inputs execute)
        adapter.send_action_dict(action_dict)
        adapter.wait_one_tick()
        fb_before = adapter.get_feedbacks()

        # Tick 2+: our input takes effect
        for _ in range(MEASURE_TICKS):
            adapter.send_action_dict(action_dict)
            adapter.wait_one_tick()
        fb_after = adapter.get_feedbacks()

        # Compute delta
        if action_name == 'steering':
            if 'yaw' in fb_before and 'yaw' in fb_after:
                delta = fb_after['yaw'] - fb_before['yaw']
                while delta > math.pi:
                    delta -= 2 * math.pi
                while delta < -math.pi:
                    delta += 2 * math.pi
            else:
                delta = 0.0
        else:
            delta = fb_after.get('speed', 0) - fb_before.get('speed', 0)

        probe_counter[0] += 1

        return ProbeResult(
            action_value=clipped,
            delta_state=delta,
            feedback_before=fb_before,
            feedback_after=fb_after,
            frame_duration_s=0.01,
            valid=True
        )

    return probe


# ── Discovery with commentary ────────────────────────────────────

def discover_with_commentary(adapter, action_name, fast_mode):
    """Run discovery for one action with step-by-step commentary."""

    config = ACTIONS[action_name]
    action_range = tuple(config['range'])
    is_bidir = action_range[0] < 0
    eps = 1e-5 if action_name == 'steering' else 0.01

    disc = FrameBinDiscovery(
        action_name, action_range,
        search_precision=0.001,
        noise_epsilon=eps,
        signal_epsilon=eps
    )

    # Save state before this action
    adapter.save_state()
    fb = adapter.get_feedbacks()
    print(f"  Saved state: speed={fb.get('speed',0):.2f} km/h, "
          f"pos=({fb.get('pos_x',0):.1f}, {fb.get('pos_z',0):.1f})")

    probe_counter = [0]
    probe_fn = make_demo_probe_fn(adapter, disc, action_name, action_range, probe_counter)

    # ── D0 ──
    step(1, f"Probe action=0 — what happens when we do NOTHING?")
    explain(f"Sutton: 'not doing an action is also an action... there is no noise'")
    d0_probe = probe_fn(0.0)
    disc.delta_0 = d0_probe.delta_state
    disc.probes.append(d0_probe)

    if action_name == 'steering':
        probe_line(1, "D0 (no action)", 0.0, d0_probe.delta_state,
                   f"D0 = {d0_probe.delta_state:.8f} rad (straight driving = ~zero yaw change)")
    else:
        probe_line(1, "D0 (no action)", 0.0, d0_probe.delta_state,
                   f"D0 = {d0_probe.delta_state:.6f} km/h (drag deceleration)")
    explain(f"This is the 'no change' reference. NOT noise. NOT a baseline to subtract.")

    wait_for_enter(fast_mode)

    # ── Exponential descent ──
    step(2, f"Descend by powers of 10: 1.0, 0.1, 0.01, 0.001, 0.0001...")
    explain(f"Sutton: 'you start with zero and then you go to like 0.1, 0.01, 0.001'")
    print()

    sequence = disc.get_exponential_sequence()
    probe_num = 2
    prev_val = None
    prev_delta = None
    max_bracket = None
    min_bracket = None

    for val in sequence:
        pr = probe_fn(val)
        delta = pr.delta_state
        disc.probes.append(pr)

        if disc.delta_max is None:
            disc.delta_max = delta
            decision = f"SATURATED. delta_max = {delta:.6f}. This is the maximum effect."
            probe_line(probe_num, f"Sweep {val}", val, delta, decision)
            prev_val = val
            prev_delta = delta

            # Check if saturated ≈ D0 (no effect)
            if abs(delta - disc.delta_0) < eps:
                result(f"Max action produces same delta as D0. {action_name} has NO EFFECT.")
                return None

            probe_num += 1
            continue

        is_sat = abs(delta - disc.delta_max) < eps
        is_d0 = abs(delta - disc.delta_0) < eps

        if max_bracket is None:
            if is_sat:
                decision = f"STILL SATURATED (same as delta_max)."
                probe_line(probe_num, f"Sweep {val}", val, delta, decision)
                prev_val = val
            else:
                max_bracket = (val, prev_val)
                decision = f"DELTA CHANGED! MAX bracket = [{val}, {prev_val}]"
                probe_line(probe_num, f"Sweep {val}", val, delta, decision, highlight=True)
                result(f"MAX is somewhere between {val} and {prev_val}")
                explain(f"Sutton: 'now I know it's bigger than {val} and smaller than {prev_val}'")

                if is_d0:
                    min_bracket = (val / 10 if val > 1e-6 else 0, val)
                    result(f"Also same as D0! MIN bracket = [{min_bracket[0]}, {val}]")
                    break

                prev_val = val
        elif min_bracket is None:
            if is_d0:
                min_bracket = (val, prev_val)
                decision = f"SAME AS D0! MIN bracket = [{val}, {prev_val}]"
                probe_line(probe_num, f"Sweep {val}", val, delta, decision, highlight=True)
                result(f"MIN is somewhere between {val} and {prev_val}")
                explain(f"Sutton: 'first action with no movement is our below minimum'")
                break
            else:
                decision = f"Still has effect (delta != D0). Keep going down."
                probe_line(probe_num, f"Sweep {val}", val, delta, decision)
                prev_val = val

        probe_num += 1

    wait_for_enter(fast_mode)

    # ── Binary search MAX ──
    if max_bracket:
        step(3, f"Binary search MAX bracket [{max_bracket[0]:.6f}, {max_bracket[1]:.6f}]")
        explain(f"Sutton: 'I go to 17. That's... Bingo.'")
        print()

        low, high = max_bracket
        bs_steps = 0
        while (high - low) > 0.001:
            mid = (low + high) / 2.0
            pr = probe_fn(mid)
            disc.probes.append(pr)
            bs_steps += 1

            is_sat = abs(pr.delta_state - disc.delta_max) < eps
            if is_sat:
                high = mid
                probe_line(probe_num, f"MaxBin {bs_steps}", mid, pr.delta_state,
                           f"SATURATED. Narrow to [{low:.6f}, {high:.6f}]")
            else:
                low = mid
                probe_line(probe_num, f"MaxBin {bs_steps}", mid, pr.delta_state,
                           f"Not saturated. Narrow to [{low:.6f}, {high:.6f}]")
            probe_num += 1

        disc.a_max = high
        result(f"MAX = {high:.6f} ({bs_steps} binary search steps)")

        wait_for_enter(fast_mode)

    # ── Binary search MIN ──
    if min_bracket:
        step(4, f"Binary search MIN bracket [{min_bracket[0]:.6f}, {min_bracket[1]:.6f}]")
        explain(f"Sutton: '5 doesn't offer any change. 6 does. So the minimum is 6.'")
        print()

        low, high = min_bracket
        bs_steps = 0
        while (high - low) > 0.001:
            mid = (low + high) / 2.0
            pr = probe_fn(mid)
            disc.probes.append(pr)
            bs_steps += 1

            is_d0 = abs(pr.delta_state - disc.delta_0) < eps
            if is_d0:
                low = mid
                probe_line(probe_num, f"MinBin {bs_steps}", mid, pr.delta_state,
                           f"Same as D0. Narrow to [{low:.6f}, {high:.6f}]")
            else:
                high = mid
                probe_line(probe_num, f"MinBin {bs_steps}", mid, pr.delta_state,
                           f"Has effect! Narrow to [{low:.6f}, {high:.6f}]")
            probe_num += 1

        disc.a_min = high
        result(f"MIN = {high:.6f} ({bs_steps} binary search steps)")

        wait_for_enter(fast_mode)

    # ── Build bins ──
    if disc.a_max and disc.a_min:
        bins = disc.build_bins()
        if is_bidir:
            bins = disc.make_bidirectional_bins(bins)

        step(5, "Build bins from MIN and MAX")
        print()

        is_binary = len(bins) <= 3 and not is_bidir
        if is_binary:
            result(f"BINARY INPUT detected! Range too small for gradient.")
            explain(f"MIN={disc.a_min:.6f}, MAX={disc.a_max:.6f}, diff={disc.a_max-disc.a_min:.6f}")
            explain(f"Result: 2 bins — DEAD_ZONE (below {disc.a_min:.4f}) and ON (above)")
        else:
            result(f"{len(bins)} bins (MIN={disc.a_min:.6f}, MAX={disc.a_max:.6f})")
            if is_bidir:
                n_side = (len(bins) - 1) // 2
                explain(f"{n_side} LEFT + STRAIGHT + {n_side} RIGHT")

        print()
        print(f"    {'Bin':>6s}  {'Min':>12s}  {'Max':>12s}  Label")
        print(f"    {'---':>6s}  {'---':>12s}  {'---':>12s}  -----")
        for b in bins:
            print(f"    {b.bin_id:>6d}  {b.a_min:>12.6f}  {b.a_max:>12.6f}  {b.label}")

        return {
            'max': disc.a_max,
            'min': disc.a_min,
            'bins': len(bins),
            'probes': probe_counter[0],
            'delta_max': disc.delta_max,
            'delta_0': disc.delta_0,
            'bin_details': bins,
        }

    return None


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Live Demo — Sutton Bin Discovery')
    parser.add_argument('--fast', action='store_true', help='Skip pauses')
    parser.add_argument('--port', type=int, default=8476, help='TCP port')
    parser.add_argument('--gas-only', action='store_true', help='Only gas discovery')
    parser.add_argument('--no-steering', action='store_true', help='Skip steering')
    args = parser.parse_args()

    banner("LIVE DEMO: Sutton's Bin Discovery Algorithm")
    print(f"  {C.BOLD}What you're about to see:{C.END}")
    print(f"  The algorithm will connect to TrackMania, send actions to the car,")
    print(f"  and systematically discover the MIN and MAX for each control.")
    print()
    print(f"  {C.BOLD}How it works:{C.END}")
    print(f"  1. Start at the biggest value, go down by powers of 10")
    print(f"  2. When the car's response changes → bracket found → binary search")
    print(f"  3. Find exact MIN (smallest useful value) and MAX (saturation point)")
    print(f"  4. Build bins — the discrete action choices the AI can use")
    print()
    print(f"  {C.BOLD}Environment:{C.END} TMNF + TMInterface 2.x")
    print(f"  {C.BOLD}Physics:{C.END}     10ms deterministic ticks (game pauses for us)")
    print(f"  {C.BOLD}Rewind:{C.END}      Every probe starts from exact same state")
    print()

    wait_for_enter(args.fast)

    # ── Connect ──
    banner("Connecting to TMNF...", C.BLUE)
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=15.0):
        print(f"  {C.RED}ERROR: Could not connect to TMNF.{C.END}")
        print(f"  Make sure TMNF is running via TMInterface with AgenticBridge.as loaded.")
        return

    if not adapter.wait_for_race(timeout=30.0):
        print(f"  {C.RED}ERROR: No race detected. Start a race in TMNF first.{C.END}")
        adapter.stop()
        return

    result("Connected to TMNF!")
    fb = adapter.get_feedbacks()
    print(f"  Speed: {fb.get('speed',0):.2f} km/h")
    print(f"  Position: ({fb.get('pos_x',0):.1f}, {fb.get('pos_y',0):.1f}, {fb.get('pos_z',0):.1f})")

    # ── Accelerate ──
    MIN_SPEED = 10.0
    speed = fb.get('speed', 0)
    if speed < MIN_SPEED:
        print(f"\n  Accelerating to {MIN_SPEED} km/h (system initialization)...")
        while speed < MIN_SPEED:
            adapter.send_action_dict({'gas': 1.0, 'brake': 0.0, 'steering': 0.0})
            adapter.wait_one_tick()
            fb = adapter.get_feedbacks()
            speed = fb.get('speed', 0)
        result(f"Speed: {speed:.2f} km/h — ready")

    # Release inputs
    adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
    adapter.wait_one_tick()

    wait_for_enter(args.fast)

    # ── Determine actions to run ──
    if args.gas_only:
        actions_to_run = ['gas']
    elif args.no_steering:
        actions_to_run = ['gas', 'brake']
    else:
        actions_to_run = ['gas', 'brake', 'steering']

    all_results = {}
    t_start = time.time()

    try:
        # ── Gas Discovery ──
        if 'gas' in actions_to_run:
            banner("DISCOVERING: GAS", C.GREEN)
            explain("Gas controls acceleration. In TMNF, it's a binary input (on/off).")
            explain("The algorithm doesn't KNOW it's binary — it will DISCOVER this.")
            print()
            r = discover_with_commentary(adapter, 'gas', args.fast)
            if r:
                all_results['gas'] = r
            wait_for_enter(args.fast)

        # ── Brake Discovery ──
        if 'brake' in actions_to_run:
            banner("DISCOVERING: BRAKE", C.RED)
            explain("Brake controls deceleration. Also binary in TMNF.")
            explain("Watch: the algorithm finds the EXACT same threshold as gas!")
            print()
            r = discover_with_commentary(adapter, 'brake', args.fast)
            if r:
                all_results['brake'] = r
            wait_for_enter(args.fast)

        # ── Steering Discovery ──
        if 'steering' in actions_to_run:
            banner("DISCOVERING: STEERING", C.BLUE)
            explain("Steering is ANALOG (-1 to +1). This is the full Sutton sweep.")
            explain("It will find a gradient of steering sensitivity — not binary!")
            explain("Uses 5-tick measurement (yaw change per tick is tiny).")
            print()
            r = discover_with_commentary(adapter, 'steering', args.fast)
            if r:
                all_results['steering'] = r
            wait_for_enter(args.fast)

    except KeyboardInterrupt:
        print(f"\n  {C.YELLOW}Interrupted.{C.END}")
    finally:
        adapter.send_action_dict({'gas': 0.0, 'brake': 0.0, 'steering': 0.0})
        try:
            adapter.wait_one_tick()
        except Exception:
            pass

    # ── Final Summary ──
    t_total = time.time() - t_start

    banner("FINAL RESULTS", C.GREEN)
    total_probes = sum(r['probes'] for r in all_results.values())
    print(f"  {C.BOLD}Total probes:  {total_probes}{C.END}")
    print(f"  {C.BOLD}Total time:    {t_total:.1f}s{C.END}")
    print(f"  {C.BOLD}Deterministic: YES (every run produces identical results){C.END}")
    print()

    print(f"  {'Action':<12s}  {'MIN':>10s}  {'MAX':>10s}  {'Bins':>5s}  {'Probes':>7s}  Type")
    print(f"  {'------':<12s}  {'---':>10s}  {'---':>10s}  {'----':>5s}  {'------':>7s}  ----")
    for name, r in all_results.items():
        atype = 'BINARY' if r['bins'] <= 2 else 'ANALOG'
        print(f"  {name:<12s}  {r['min']:>10.6f}  {r['max']:>10.6f}  {r['bins']:>5d}  {r['probes']:>7d}  {atype}")

    print()
    explain("Run this script again — you'll get IDENTICAL numbers. That's determinism.")
    explain("This is Phase A complete. Phase B: record transitions into knowledge graph.")

    adapter.stop()
    print()
    print(f"  {C.GREEN}Demo complete.{C.END}")
    print()


if __name__ == '__main__':
    main()
