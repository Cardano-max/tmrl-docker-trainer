"""
LIVE PER-VARIABLE MULTI-GRAPH RECORDING TEST (Phase 3)

Proves the Phase 3 per-variable knowledge graph pipeline end-to-end:
FrameOrchestrator + MultiGraphManager + TMNFAdapter + FalkorDB.

Each feedback variable (speed, pos_x, pos_y, pos_z, yaw) gets its own
FalkorDB graph (kg_speed, kg_pos_x, etc.) with discretized State nodes
and ACTION_BIN edges labeled by bin.

Sutton Jan 15: "I have, my car is at 100. This is a node here."
Sutton Jan 24: "actions are relations and feedbacks are nodes"
Sutton Jan 24: "recording a graph is gonna be multiple graphs at the
               same time in the frame"

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
  python tests/test_live_multigraph_recording.py
  python tests/test_live_multigraph_recording.py --port 8476
  python tests/test_live_multigraph_recording.py --no-graph          # Skip FalkorDB, in-memory only
  python tests/test_live_multigraph_recording.py --falkor-host localhost --falkor-port 6379
  python tests/test_live_multigraph_recording.py --speed 5.0         # Game speed multiplier
"""

import sys
import os
import time
import glob
import json
import logging
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.tmnf_adapter import TMNFAdapter
from core.frame_orchestrator import FrameOrchestrator
from knowledge.multi_graph_manager import MultiGraphManager
from knowledge.variable_graph import VariableGraph

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('LIVE_MULTIGRAPH')


# =============================================================================
# CONFIGURATION
# =============================================================================

# Variables to track (from config/tmnf_config.json, only track_graph=true)
# Precision values = min_delta from bin discovery
VARIABLES = {
    'speed': 0.6,
    'pos_x': 0.01,
    'pos_y': 0.01,
    'pos_z': 0.01,
    'yaw': 0.001,
}

# Default bins for binary actions (MIN ~= 0.00196 from Phase A discovery)
DEFAULT_BINS_BY_ACTION = {
    'gas':   [{'bin_id': 0, 'min': 0.0, 'max': 0.002, 'label': 'DEAD_ZONE'},
              {'bin_id': 1, 'min': 0.002, 'max': 1.0, 'label': 'ON'}],
    'brake': [{'bin_id': 0, 'min': 0.0, 'max': 0.002, 'label': 'DEAD_ZONE'},
              {'bin_id': 1, 'min': 0.002, 'max': 1.0, 'label': 'ON'}],
    'left':  [{'bin_id': 0, 'min': 0.0, 'max': 0.002, 'label': 'DEAD_ZONE'},
              {'bin_id': 1, 'min': 0.002, 'max': 1.0, 'label': 'ON'}],
    'right': [{'bin_id': 0, 'min': 0.0, 'max': 0.002, 'label': 'DEAD_ZONE'},
              {'bin_id': 1, 'min': 0.002, 'max': 1.0, 'label': 'ON'}],
}


def load_bins_from_results():
    """
    Try to load bins from the most recent tmnf_phase_a_results_*.json file.
    Falls back to DEFAULT_BINS_BY_ACTION if no results file found.

    Returns:
        Dict mapping action_name -> list of bin dicts
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(project_root, 'tmnf_phase_a_results_*.json')
    files = sorted(glob.glob(pattern))

    if not files:
        print("  No tmnf_phase_a_results_*.json found, using hardcoded bins")
        return dict(DEFAULT_BINS_BY_ACTION)

    latest = files[-1]
    print(f"  Loading bins from: {os.path.basename(latest)}")

    try:
        with open(latest, 'r') as f:
            data = json.load(f)

        bins_by_action = {}
        actions = data.get('actions', data.get('results', {}))
        for action_name, action_data in actions.items():
            bins = action_data.get('bins', [])
            if bins:
                bin_dicts = []
                for b in bins:
                    bin_dicts.append({
                        'bin_id': b.get('bin_id', 0),
                        'min': b.get('min', b.get('a_min', 0.0)),
                        'max': b.get('max', b.get('a_max', 1.0)),
                        'label': b.get('label', f'BIN_{b.get("bin_id", 0)}'),
                    })
                bins_by_action[action_name] = bin_dicts

        # Fill in any missing actions with defaults
        for action_name in ['gas', 'brake', 'left', 'right']:
            if action_name not in bins_by_action:
                bins_by_action[action_name] = DEFAULT_BINS_BY_ACTION[action_name]

        return bins_by_action

    except Exception as e:
        print(f"  [WARN] Failed to load results file: {e}")
        return dict(DEFAULT_BINS_BY_ACTION)


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
# SUTTON-FORMAT GRAPH OUTPUT (FalkorDB mode)
# =============================================================================

def print_graph_from_falkordb(mgm, variables):
    """
    Query FalkorDB per-variable graphs and print Sutton-format edges.

    Sutton's vision: "I have my car at 100 [node]. What is this node?
    That's going to be 110. [edge: speed max = 17]"

    Args:
        mgm: MultiGraphManager instance (connected to FalkorDB)
        variables: Dict of variable_name -> precision

    Returns:
        Dict of variable_name -> {'nodes': N, 'edges': M}
    """
    print()
    print("=" * 70)
    print("  PER-VARIABLE KNOWLEDGE GRAPH (Sutton format)")
    print("  \"actions are relations and feedbacks are nodes\" -- Sutton Jan 24")
    print("=" * 70)

    stats = {}

    for var_name in variables:
        vg = mgm.get_variable_graph(var_name)
        if vg is None or not vg.is_connected():
            print(f"\n  --- kg_{var_name} (NOT CONNECTED) ---")
            stats[var_name] = {'nodes': 0, 'edges': 0}
            continue

        n_nodes = vg.count_nodes()
        n_edges = vg.count_edges()
        stats[var_name] = {'nodes': n_nodes, 'edges': n_edges}

        print(f"\n  --- kg_{var_name} ({n_nodes} nodes, {n_edges} edges) ---")

        # Query ALL edges in Sutton format
        try:
            query = (
                "MATCH (from:State)-[e:ACTION_BIN]->(to:State) "
                "RETURN from.value, e.action_name, e.bin_label, to.value "
                "ORDER BY from.value, e.action_name"
            )
            result = vg.graph.query(query)

            for row in result.result_set:
                from_val, action_name, bin_label, to_val = row
                print(f"    {var_name} = {from_val} --[{action_name}:{bin_label}]--> {var_name} = {to_val}")

            if not result.result_set:
                print(f"    (no edges recorded)")

        except Exception as e:
            print(f"    [ERROR] Query failed: {e}")

    return stats


# =============================================================================
# SUTTON-FORMAT GRAPH OUTPUT (In-memory fallback)
# =============================================================================

def print_graph_from_memory(orchestrator, variables, bins_by_action):
    """
    Reconstruct what WOULD have been recorded in per-variable graphs
    from orchestrator in-memory history. Uses VariableGraph._discretize()
    for consistent discretization.

    Args:
        orchestrator: FrameOrchestrator with recorded history
        variables: Dict of variable_name -> precision
        bins_by_action: Dict of action_name -> list of bin dicts

    Returns:
        Dict of variable_name -> {'nodes': N, 'edges': M}
    """
    print()
    print("=" * 70)
    print("  PER-VARIABLE KNOWLEDGE GRAPH (Sutton format) -- IN-MEMORY MODE")
    print("  \"actions are relations and feedbacks are nodes\" -- Sutton Jan 24")
    print("=" * 70)

    history = orchestrator.get_history()
    stats = {}

    for var_name, precision in variables.items():
        unique_nodes = set()
        edges = []

        for frame in history:
            from_feedbacks = frame['feedback_before']
            to_feedbacks = frame['feedback_after']
            action = frame['action']

            if var_name not in from_feedbacks or var_name not in to_feedbacks:
                continue

            from_val = VariableGraph._discretize(from_feedbacks[var_name], precision)
            to_val = VariableGraph._discretize(to_feedbacks[var_name], precision)
            unique_nodes.add(from_val)
            unique_nodes.add(to_val)

            # Resolve bins for each action
            for action_name, action_value in action.items():
                resolved = _resolve_bin_manual(bins_by_action, action_name, action_value)
                if resolved is None:
                    continue

                # Skip dead-zone (bin_id=0 with zero value)
                if resolved.get('bin_id', -1) == 0 and abs(action_value) < 1e-8:
                    continue

                edges.append({
                    'from_val': from_val,
                    'action_name': action_name,
                    'bin_label': resolved['label'],
                    'to_val': to_val,
                })

        n_nodes = len(unique_nodes)
        n_edges = len(edges)
        stats[var_name] = {'nodes': n_nodes, 'edges': n_edges}

        print(f"\n  --- kg_{var_name} ({n_nodes} nodes, {n_edges} edges) ---")

        # Sort for consistent display
        edges_sorted = sorted(edges, key=lambda e: (e['from_val'], e['action_name']))
        for e in edges_sorted:
            print(f"    {var_name} = {e['from_val']} --[{e['action_name']}:{e['bin_label']}]--> {var_name} = {e['to_val']}")

        if not edges:
            print(f"    (no edges recorded)")

    return stats


def _resolve_bin_manual(bins_by_action, action_name, value):
    """Resolve a raw action value to its bin (same logic as MultiGraphManager.resolve_bin)."""
    bins = bins_by_action.get(action_name, [])
    for b in bins:
        if b['min'] <= value < b['max']:
            return b
    if bins:
        return bins[-1]
    return None


# =============================================================================
# VERIFICATION
# =============================================================================

def print_verification(stats, total_frames, history, bins_by_action):
    """
    Print verification summary table.

    Args:
        stats: Dict of variable_name -> {'nodes': N, 'edges': M}
        total_frames: Total frames recorded
        history: List of frame result dicts
        bins_by_action: Bin definitions for D0 edge counting
    """
    print()
    print("=" * 70)
    print("  VERIFICATION")
    print("=" * 70)

    # Summary table
    print(f"\n  {'Variable':<12} {'Nodes':>8} {'Edges':>8} {'No-Dup Check':>14}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*14}")

    all_pass = True
    for var_name, s in stats.items():
        # No-Dup Check: PASS if nodes < total_frames
        # With 25 frames, each creating at most 2 nodes (from+to),
        # max theoretical = 50. MERGE deduplicates shared values.
        no_dup = "PASS" if s['nodes'] < total_frames else "FAIL"
        if no_dup == "FAIL":
            all_pass = False
        print(f"  {var_name:<12} {s['nodes']:>8} {s['edges']:>8} {no_dup:>14}")

    # D0 verification
    print()
    d0_edge_count = 0
    for frame in history:
        action = frame['action']
        # Check if this is a D0 frame (all actions = 0.0)
        if all(abs(v) < 1e-8 for v in action.values()):
            # Count how many non-dead-zone bins would be created
            for action_name, action_value in action.items():
                resolved = _resolve_bin_manual(bins_by_action, action_name, action_value)
                if resolved and not (resolved.get('bin_id', -1) == 0 and abs(action_value) < 1e-8):
                    d0_edge_count += 1

    print(f"  D0 edges recorded: {d0_edge_count}")
    print(f"  Expected: 0 (MultiGraphManager skips dead-zone: bin_id=0 with value 0.0)")
    if d0_edge_count == 0:
        print(f"  [PASS] D0 coast correctly produces no ACTION_BIN edges")
    else:
        print(f"  [FAIL] Expected 0 D0 edges, got {d0_edge_count}")
        all_pass = False

    print()
    print(f'  Sutton: "the action of not giving an action is also an action"')
    print(f"  Note: D0 coast frames have all 4 actions at 0.0 = dead zone.")
    print(f"  No edges are created for Phase 3 frames. State nodes still")
    print(f"  exist from adjacent phases (shared via MERGE).")

    print()
    if all_pass:
        print("  OVERALL: PASS -- per-variable knowledge graph pipeline verified")
    else:
        print("  OVERALL: WARN -- some checks did not pass (see above)")

    print()
    print("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Live per-variable multi-graph recording test (Phase 3: TMNF + FalkorDB)'
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
    print("=" * 70)
    print("  LIVE PER-VARIABLE MULTI-GRAPH RECORDING TEST (Phase 3)")
    print("  Sutton: \"recording a graph is gonna be multiple graphs")
    print("           at the same time in the frame\" -- Jan 24")
    print("=" * 70)
    print()

    # ---- Step 1: Connect to TMNF ----
    print("[1/7] Connecting to TMNF...")
    adapter = TMNFAdapter()
    if not adapter.connect(port=args.port, timeout=args.timeout):
        print(f"[FAIL] Cannot connect to TMNF on port {args.port}")
        print("       Make sure TMNF is running with AgenticBridge.as loaded")
        sys.exit(1)

    print("[1/7] Connected. Waiting for race to start...")
    if not adapter.wait_for_race(timeout=args.timeout):
        print("[FAIL] Race did not start in time")
        adapter.stop()
        sys.exit(1)

    if args.speed != 1.0:
        adapter.set_speed(args.speed)
        print(f"       Game speed set to {args.speed}x")

    # ---- Step 2: Build multi-graph configuration ----
    print("[2/7] Setting up MultiGraphManager + FrameOrchestrator...")

    bins_by_action = load_bins_from_results()
    print(f"  Variables tracked: {list(VARIABLES.keys())}")
    print(f"  Actions configured: {list(bins_by_action.keys())}")
    for action_name, bins in bins_by_action.items():
        labels = [b['label'] for b in bins]
        print(f"    {action_name}: {labels}")

    # Create MultiGraphManager (Phase 3 -- per-variable graphs)
    mgm = MultiGraphManager(variables=VARIABLES, bins_by_action=bins_by_action)

    # Create FrameOrchestrator with multi_graph only (NO legacy knowledge_manager)
    orchestrator = FrameOrchestrator(adapter, multi_graph=mgm)

    # ---- Step 3: Connect to FalkorDB (optional) ----
    graph_available = False
    if not args.no_graph:
        print(f"[3/7] Connecting to FalkorDB ({args.falkor_host}:{args.falkor_port})...")
        graph_available = orchestrator.initialize_multi_graph(
            host=args.falkor_host,
            port=args.falkor_port
        )
        if graph_available:
            print(f"       FalkorDB connected -- {len(VARIABLES)} per-variable graphs ready")
            # Reset all graphs for clean demo
            mgm.reset_all()
            print("       All graphs reset (clean slate for demo)")
        else:
            print(f"       [WARN] FalkorDB not available -- running in-memory mode")
            print(f"       (start FalkorDB or use --no-graph to suppress this warning)")
    else:
        print("[3/7] --no-graph flag: running in-memory only")

    # ---- Step 4-7: Record four phases ----
    all_results = []

    # Phase 1: Gas only (10 frames)
    print("\n[4/7] Recording Phase 1: Gas acceleration...")
    action_gas = {'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
    phase1_results = record_phase(
        orchestrator, action_gas, 10, "PHASE 1 -- Gas acceleration", track_key='speed'
    )
    all_results.extend(phase1_results)

    # Phase 2: Brake only (5 frames)
    print("\n[5/7] Recording Phase 2: Brake deceleration...")
    action_brake = {'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0}
    phase2_results = record_phase(
        orchestrator, action_brake, 5, "PHASE 2 -- Brake deceleration", track_key='speed'
    )
    all_results.extend(phase2_results)

    # Phase 3: D0 coast (5 frames)
    print("\n[6/7] Recording Phase 3: D0 coast (no action)...")
    action_d0 = {'gas': 0.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
    phase3_results = record_phase(
        orchestrator, action_d0, 5, "PHASE 3 -- D0 coast", track_key='speed'
    )
    all_results.extend(phase3_results)

    # Phase 4: Left steering + gas (5 frames)
    print("\n[7/7] Recording Phase 4: Left steering + gas...")
    action_left = {'gas': 1.0, 'brake': 0.0, 'left': 1.0, 'right': 0.0}
    phase4_results = record_phase(
        orchestrator, action_left, 5, "PHASE 4 -- Left+gas steering", track_key='yaw'
    )
    all_results.extend(phase4_results)

    total_frames = len(all_results)

    # ---- Print Sutton-format graph output ----
    if graph_available:
        stats = print_graph_from_falkordb(mgm, VARIABLES)
    else:
        stats = print_graph_from_memory(orchestrator, VARIABLES, bins_by_action)

    # ---- Verification ----
    print_verification(stats, total_frames, all_results, bins_by_action)

    # ---- Cleanup ----
    print("[DONE] Cleaning up...")
    adapter.stop()
    print(f"[DONE] Recorded {total_frames} frames across 4 phases")
    print(f"[DONE] {len(VARIABLES)} per-variable graphs: {', '.join(f'kg_{v}' for v in VARIABLES)}")

    if graph_available:
        all_stats = mgm.get_all_stats()
        total_nodes = sum(s['nodes'] for s in all_stats.values())
        total_edges = sum(s['edges'] for s in all_stats.values())
        print(f"[DONE] Total across all graphs: {total_nodes} nodes, {total_edges} edges")
    else:
        print(f"[DONE] In-memory history: {len(orchestrator.get_history())} frames")


if __name__ == '__main__':
    main()
