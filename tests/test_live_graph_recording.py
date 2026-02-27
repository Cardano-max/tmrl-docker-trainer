"""
LIVE GRAPH RECORDING TEST -- Per-Frame State Transitions into Knowledge Graph

Proves the full pipeline end-to-end: FrameOrchestrator + TMNF + FalkorDB.

Sutton quote: "the system should be able to record one node per frame" -- Jan 15
Sutton quote: "recording a graph is gonna be multiple graphs at the same time
               in the frame" -- Jan 24

Phases:
  1. Gas only       (10 frames) -- acceleration
  2. Brake only     (5 frames)  -- deceleration
  3. No action (D0) (5 frames)  -- coast ("not doing an action is also an action")
  4. Left + gas     (5 frames)  -- steering (yaw change)

REQUIRES:
  - TMNF + TMInterface 2.x with AgenticBridge.as plugin loaded
  - An active race (countdown finished)
  - Optional: FalkorDB on localhost:6379 (runs in-memory mode without it)

USAGE:
  python tests/test_live_graph_recording.py
  python tests/test_live_graph_recording.py --port 8476
  python tests/test_live_graph_recording.py --no-graph          # Skip FalkorDB, in-memory only
  python tests/test_live_graph_recording.py --falkor-host localhost --falkor-port 6379
  python tests/test_live_graph_recording.py --speed 5.0         # Game speed multiplier
"""

import sys
import os
import time
import logging
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.tmnf_adapter import TMNFAdapter
from core.frame_orchestrator import FrameOrchestrator
from knowledge.knowledge_manager import KnowledgeManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('LIVE_GRAPH')


# =============================================================================
# PHASE RECORDING
# =============================================================================

def record_phase(orchestrator, action, num_frames, phase_name, track_key='speed'):
    """
    Record N frames with a fixed action, printing per-frame state.

    Args:
        orchestrator: FrameOrchestrator instance
        action: Action dict to apply each frame
        num_frames: How many frames to record
        phase_name: Display name for this phase
        track_key: Feedback key to track (speed or yaw)

    Returns:
        List of frame results
    """
    print(f"\n  --- {phase_name} ({num_frames} frames) ---")
    results = []
    for i in range(num_frames):
        result = orchestrator.execute_one_frame(action)
        before_val = result['feedback_before'].get(track_key, 0.0)
        after_val = result['feedback_after'].get(track_key, 0.0)

        # Format display
        if track_key == 'speed':
            print(f"    Frame {result['frame_id']:3d}: speed {before_val:8.3f} -> {after_val:8.3f} km/h  ({phase_name})")
        elif track_key == 'yaw':
            print(f"    Frame {result['frame_id']:3d}: yaw {before_val:10.6f} -> {after_val:10.6f} rad  ({phase_name})")
        else:
            print(f"    Frame {result['frame_id']:3d}: {track_key} {before_val:.6f} -> {after_val:.6f}  ({phase_name})")

        results.append(result)
    return results


# =============================================================================
# GRAPH VERIFICATION
# =============================================================================

def verify_graph_edges(knowledge, phase_results, expected_action, phase_name):
    """
    Verify that graph edges have correct action properties (including left/right).

    Task 2: Verify KnowledgeManager Cypher includes left/right.

    Args:
        knowledge: KnowledgeManager instance
        phase_results: List of frame results from this phase
        expected_action: Expected action dict
        phase_name: Phase name for display

    Returns:
        (passed, total) verification counts
    """
    passed = 0
    total = 0

    for result in phase_results:
        frame_id = result['frame_id']
        action_data = knowledge.get_action_at_frame(frame_id)
        if action_data is None:
            print(f"    [WARN] No edge found for frame {frame_id}")
            total += 1
            continue

        total += 1

        # Check all expected properties exist
        checks_ok = True
        for key in ['gas', 'brake', 'steering', 'left', 'right']:
            if key not in action_data:
                print(f"    [FAIL] Frame {frame_id}: missing '{key}' in edge")
                checks_ok = False

        # Check expected values match
        if checks_ok:
            for key, expected_val in expected_action.items():
                actual_val = action_data.get(key, None)
                if actual_val is not None and abs(actual_val - expected_val) > 0.01:
                    print(f"    [FAIL] Frame {frame_id}: {key} expected {expected_val}, got {actual_val}")
                    checks_ok = False

        if checks_ok:
            passed += 1

    return passed, total


def verify_graph_completeness(knowledge, total_frames_recorded):
    """
    Verify graph node and edge counts.

    Args:
        knowledge: KnowledgeManager instance
        total_frames_recorded: Total frames we recorded

    Returns:
        (node_count, edge_count, expected_nodes, expected_edges)
    """
    node_count = knowledge.count_frames()
    edge_count = knowledge.count_transitions()
    # N frames recorded -> N+1 nodes (from_frame_0 + N to_frames), N edges
    expected_nodes = total_frames_recorded + 1
    expected_edges = total_frames_recorded
    return node_count, edge_count, expected_nodes, expected_edges


# =============================================================================
# SUMMARY DISPLAY
# =============================================================================

def print_summary(all_results, phase_slices, graph_available, knowledge, total_frames):
    """
    Print the final summary table.

    Args:
        all_results: All frame results in order
        phase_slices: Dict mapping phase name to (start_idx, count, track_key)
        graph_available: Whether FalkorDB is connected
        knowledge: KnowledgeManager instance (or None)
        total_frames: Total frames recorded
    """
    print()
    print("=" * 66)
    print("  LIVE GRAPH RECORDING -- RESULTS")
    print("=" * 66)

    # Node/edge counts
    if graph_available and knowledge:
        node_count, edge_count, exp_nodes, exp_edges = verify_graph_completeness(
            knowledge, total_frames
        )
        print(f"\n  Total frames recorded: {total_frames}")
        print(f"  Graph nodes: {node_count}  (expected {exp_nodes}: {total_frames} frames + 1 initial)")
        print(f"  Graph edges: {edge_count}  (expected {exp_edges}: one per transition)")
        if node_count == exp_nodes and edge_count == exp_edges:
            print("  [PASS] Graph counts match expected")
        else:
            print("  [WARN] Graph counts differ from expected")
    else:
        print(f"\n  Total frames recorded: {total_frames}")
        print(f"  Graph: IN-MEMORY ONLY (FalkorDB not connected)")
        print(f"  In-memory history: {len(all_results)} frames")

    # Per-phase summaries
    offset = 0
    for phase_name, (action, count, track_key) in phase_slices.items():
        phase_results = all_results[offset:offset + count]
        offset += count

        if not phase_results:
            continue

        print(f"\n  {phase_name}:")

        # Extract tracked values
        values = []
        # First value is feedback_before of first frame
        first_before = phase_results[0]['feedback_before'].get(track_key, 0.0)
        values.append(first_before)
        for r in phase_results:
            values.append(r['feedback_after'].get(track_key, 0.0))

        # Format value sequence (show first 3 + last value)
        if len(values) <= 5:
            val_str = " -> ".join(f"{v:.1f}" for v in values)
        else:
            val_str = (
                " -> ".join(f"{v:.1f}" for v in values[:3])
                + " -> ... -> "
                + f"{values[-1]:.1f}"
            )

        unit = "km/h" if track_key == 'speed' else "rad"
        print(f"    {track_key.capitalize()}: {val_str} {unit}")

        # Show action dict
        action_str = ", ".join(f"{k}: {v}" for k, v in action.items())
        print(f"    All edges: {{{action_str}}}")

        # Sutton quote for D0
        if all(v == 0.0 for v in action.values()):
            print('    Sutton: "not doing an action is also an action"')

    # Graph query examples (if graph available)
    if graph_available and knowledge:
        print(f"\n  GRAPH QUERY EXAMPLES:")
        # Show sample transitions
        sample_frames = [0, 10, 15]
        for fid in sample_frames:
            if fid >= total_frames:
                continue
            transitions = knowledge.get_transitions_from_frame(fid)
            if transitions:
                t = transitions[0]
                action_parts = []
                if t['action'].get('gas', 0) > 0:
                    action_parts.append(f"gas={t['action']['gas']}")
                if t['action'].get('brake', 0) > 0:
                    action_parts.append(f"brake={t['action']['brake']}")
                if t['action'].get('left', 0) > 0:
                    action_parts.append(f"left={t['action']['left']}")
                if t['action'].get('right', 0) > 0:
                    action_parts.append(f"right={t['action']['right']}")
                if not action_parts:
                    action_parts.append("D0")
                action_label = ", ".join(action_parts)

                # Get speed from frames
                from_frame = knowledge.get_frame(fid)
                to_frame = knowledge.get_frame(fid + 1)
                from_speed = from_frame.get('speed', 0.0) if from_frame else 0.0
                to_speed = to_frame.get('speed', 0.0) if to_frame else 0.0
                print(f"    Frame {fid} -> Frame {fid + 1}: {action_label} -> speed {from_speed:.1f}->{to_speed:.1f}")

    # Edge property verification (Task 2)
    if graph_available and knowledge:
        print(f"\n  EDGE PROPERTY VERIFICATION (left/right in Cypher):")
        # Check phase 4 edges (left steering) have left=1.0
        phase4_start = 20  # After gas(10) + brake(5) + D0(5)
        if phase4_start < total_frames:
            action_data = knowledge.get_action_at_frame(phase4_start)
            if action_data:
                left_val = action_data.get('left', 'MISSING')
                right_val = action_data.get('right', 'MISSING')
                print(f"    Phase 4 edge (frame {phase4_start}): left={left_val}, right={right_val}")
                if left_val == 1.0:
                    print("    [PASS] left=1.0 in graph edge")
                else:
                    print(f"    [FAIL] Expected left=1.0, got {left_val}")

        # Check phase 1 edges (gas only) have left=0.0, right=0.0
        action_data = knowledge.get_action_at_frame(0)
        if action_data:
            left_val = action_data.get('left', 'MISSING')
            right_val = action_data.get('right', 'MISSING')
            print(f"    Phase 1 edge (frame 0): left={left_val}, right={right_val}")
            if left_val == 0.0 and right_val == 0.0:
                print("    [PASS] left=0.0, right=0.0 explicitly stored")
            else:
                print(f"    [FAIL] Expected left=0.0, right=0.0")

    print()
    print("=" * 66)


# =============================================================================
# IN-MEMORY SUMMARY (when FalkorDB unavailable)
# =============================================================================

def print_in_memory_summary(orchestrator, all_results, phase_slices, total_frames):
    """
    Print summary using only in-memory history (no graph queries).
    """
    print()
    print("=" * 66)
    print("  LIVE GRAPH RECORDING -- RESULTS (IN-MEMORY MODE)")
    print("=" * 66)

    print(f"\n  Total frames recorded: {total_frames}")
    print(f"  In-memory history: {len(orchestrator.get_history())} frames")
    print(f"  Graph: NOT CONNECTED (--no-graph or FalkorDB unavailable)")

    offset = 0
    for phase_name, (action, count, track_key) in phase_slices.items():
        phase_results = all_results[offset:offset + count]
        offset += count

        if not phase_results:
            continue

        print(f"\n  {phase_name}:")

        values = []
        first_before = phase_results[0]['feedback_before'].get(track_key, 0.0)
        values.append(first_before)
        for r in phase_results:
            values.append(r['feedback_after'].get(track_key, 0.0))

        if len(values) <= 5:
            val_str = " -> ".join(f"{v:.1f}" for v in values)
        else:
            val_str = (
                " -> ".join(f"{v:.1f}" for v in values[:3])
                + " -> ... -> "
                + f"{values[-1]:.1f}"
            )

        unit = "km/h" if track_key == 'speed' else "rad"
        print(f"    {track_key.capitalize()}: {val_str} {unit}")

        action_str = ", ".join(f"{k}: {v}" for k, v in action.items())
        print(f"    All edges: {{{action_str}}}")

        if all(v == 0.0 for v in action.values()):
            print('    Sutton: "not doing an action is also an action"')

    # In-memory query examples
    print(f"\n  IN-MEMORY QUERY EXAMPLES:")
    sample_frames = [0, 10, 15]
    history = orchestrator.get_history()
    for fid in sample_frames:
        if fid < len(history):
            frame = history[fid]
            action = frame['action']
            before_speed = frame['feedback_before'].get('speed', 0.0)
            after_speed = frame['feedback_after'].get('speed', 0.0)
            action_parts = []
            if action.get('gas', 0) > 0:
                action_parts.append(f"gas={action['gas']}")
            if action.get('brake', 0) > 0:
                action_parts.append(f"brake={action['brake']}")
            if action.get('left', 0) > 0:
                action_parts.append(f"left={action['left']}")
            if action.get('right', 0) > 0:
                action_parts.append(f"right={action['right']}")
            if not action_parts:
                action_parts.append("D0")
            action_label = ", ".join(action_parts)
            print(f"    Frame {fid} -> {fid + 1}: {action_label} -> speed {before_speed:.1f}->{after_speed:.1f}")

    print()
    print("=" * 66)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Live per-frame graph recording test (TMNF + FalkorDB)'
    )
    parser.add_argument('--port', type=int, default=8476,
                        help='TMInterface TCP port (default: 8476)')
    parser.add_argument('--falkor-host', type=str, default='localhost',
                        help='FalkorDB host (default: localhost)')
    parser.add_argument('--falkor-port', type=int, default=6379,
                        help='FalkorDB port (default: 6379)')
    parser.add_argument('--no-graph', action='store_true',
                        help='Skip FalkorDB, run in-memory only')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Game speed multiplier (default: 1.0)')
    parser.add_argument('--timeout', type=float, default=30.0,
                        help='Connection timeout in seconds (default: 30)')
    args = parser.parse_args()

    print()
    print("=" * 66)
    print("  LIVE PER-FRAME GRAPH RECORDING TEST")
    print("  Sutton: 'the system should be able to record one node per frame'")
    print("=" * 66)
    print()

    # ---- Step 1: Connect to TMNF ----
    print("[1/6] Connecting to TMNF...")
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=args.timeout):
        print(f"[FAIL] Cannot connect to TMNF on port {args.port}")
        print("       Make sure TMNF is running with AgenticBridge.as loaded")
        sys.exit(1)

    print("[1/6] Connected. Waiting for race to start...")
    if not adapter.wait_for_race(timeout=args.timeout):
        print("[FAIL] Race did not start in time")
        adapter.stop()
        sys.exit(1)

    if args.speed != 1.0:
        adapter.set_speed(args.speed)
        print(f"       Game speed set to {args.speed}x")

    # ---- Step 2: Set up orchestrator + knowledge ----
    print("[2/6] Setting up FrameOrchestrator + KnowledgeManager...")
    knowledge = KnowledgeManager(graph_name="live_recording_test")
    orchestrator = FrameOrchestrator(adapter, knowledge_manager=knowledge)

    graph_available = False
    if not args.no_graph:
        # Task 3: Use initialize_graph() from 02-01
        graph_available = orchestrator.initialize_graph(
            host=args.falkor_host,
            port=args.falkor_port
        )
        if graph_available:
            print(f"       FalkorDB connected ({args.falkor_host}:{args.falkor_port})")
            # Reset graph for clean demo
            knowledge.reset()
            print("       Graph reset (clean slate for demo)")
        else:
            print(f"       [WARN] FalkorDB not available -- running in-memory mode")
            print(f"       (start FalkorDB or use --no-graph to suppress this warning)")
    else:
        print("       --no-graph flag: running in-memory only")

    # ---- Step 3-6: Record four phases ----
    all_results = []

    # Phase 1: Gas only (10 frames)
    print("\n[3/6] Recording Phase 1: Gas acceleration...")
    action_gas = {'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
    phase1_results = record_phase(
        orchestrator, action_gas, 10, "PHASE 1 -- Gas acceleration", track_key='speed'
    )
    all_results.extend(phase1_results)

    # Phase 2: Brake only (5 frames)
    print("\n[4/6] Recording Phase 2: Brake deceleration...")
    action_brake = {'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0}
    phase2_results = record_phase(
        orchestrator, action_brake, 5, "PHASE 2 -- Brake deceleration", track_key='speed'
    )
    all_results.extend(phase2_results)

    # Phase 3: D0 coast (5 frames)
    print("\n[5/6] Recording Phase 3: D0 coast (no action)...")
    action_d0 = {'gas': 0.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
    phase3_results = record_phase(
        orchestrator, action_d0, 5, "PHASE 3 -- D0 coast", track_key='speed'
    )
    all_results.extend(phase3_results)

    # Phase 4: Left steering + gas (5 frames)
    print("\n[6/6] Recording Phase 4: Left steering + gas...")
    action_left = {'gas': 1.0, 'brake': 0.0, 'left': 1.0, 'right': 0.0}
    phase4_results = record_phase(
        orchestrator, action_left, 5, "PHASE 4 -- Left+gas steering", track_key='yaw'
    )
    all_results.extend(phase4_results)

    total_frames = len(all_results)

    # ---- Phase slices for summary ----
    phase_slices = {
        'PHASE 1 -- Gas acceleration (10 frames)': (action_gas, 10, 'speed'),
        'PHASE 2 -- Brake deceleration (5 frames)': (action_brake, 5, 'speed'),
        'PHASE 3 -- D0 coast (5 frames)': (action_d0, 5, 'speed'),
        'PHASE 4 -- Left+gas steering (5 frames)': (action_left, 5, 'yaw'),
    }

    # ---- Display summary ----
    if graph_available:
        print_summary(all_results, phase_slices, True, knowledge, total_frames)

        # Task 2: Full edge property verification
        print("\n  FULL EDGE VERIFICATION:")
        total_passed = 0
        total_checked = 0

        p, t = verify_graph_edges(knowledge, phase1_results,
                                  {'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0},
                                  "Phase 1 (gas)")
        total_passed += p
        total_checked += t
        print(f"    Phase 1 (gas):       {p}/{t} edges correct")

        p, t = verify_graph_edges(knowledge, phase2_results,
                                  {'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0},
                                  "Phase 2 (brake)")
        total_passed += p
        total_checked += t
        print(f"    Phase 2 (brake):     {p}/{t} edges correct")

        p, t = verify_graph_edges(knowledge, phase3_results,
                                  {'gas': 0.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0},
                                  "Phase 3 (D0)")
        total_passed += p
        total_checked += t
        print(f"    Phase 3 (D0):        {p}/{t} edges correct")

        p, t = verify_graph_edges(knowledge, phase4_results,
                                  {'gas': 1.0, 'brake': 0.0, 'left': 1.0, 'right': 0.0},
                                  "Phase 4 (left+gas)")
        total_passed += p
        total_checked += t
        print(f"    Phase 4 (left+gas):  {p}/{t} edges correct")

        print(f"\n    TOTAL: {total_passed}/{total_checked} edges verified")
        if total_passed == total_checked:
            print("    [PASS] All edge properties correct (gas, brake, steering, left, right)")
        else:
            print(f"    [WARN] {total_checked - total_passed} edges had issues")
    else:
        print_in_memory_summary(orchestrator, all_results, phase_slices, total_frames)

    # ---- Cleanup ----
    print("\n[DONE] Cleaning up...")
    adapter.stop()
    print(f"[DONE] Recorded {total_frames} frames successfully")

    if graph_available:
        stats = knowledge.get_statistics()
        print(f"[DONE] Graph stats: {stats['frames']} nodes, {stats['transitions']} transitions")
    else:
        print(f"[DONE] In-memory history: {len(orchestrator.get_history())} frames")


if __name__ == '__main__':
    main()
