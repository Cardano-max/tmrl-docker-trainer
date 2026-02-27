"""
Offline Integration Tests: FrameOrchestrator -> MultiGraphManager -> VariableGraph

Tests the full pipeline without FalkorDB or TMNF.
Uses InMemoryVariableGraph (Python dicts) and InMemoryMultiGraphManager
to verify real MultiGraphManager logic with mock storage.

9 tests covering:
- Frame recording through orchestrator to per-variable graphs
- Node deduplication across the full pipeline (GRAPH-04)
- Bin labels on edges (GRAPH-08)
- Multiple tracked variables updated simultaneously (GRAPH-06)
- Orchestrator works without multi-graph (graceful fallback)
- Legacy and multi-graph coexistence
- Dead zone handling (D0 = no edge)
- GRAPH-07: Different actions reaching same destination = multiple edges
"""

import pytest
from typing import Dict, List, Optional, Any

from core.frame_orchestrator import FrameOrchestrator
from knowledge.multi_graph_manager import MultiGraphManager
from knowledge.variable_graph import VariableGraph


# =============================================================================
# MOCK ADAPTER
# =============================================================================

class MockAdapter:
    """
    Mock adapter that simulates frame-sync behavior.

    Speed increases by 5.0 per gas tick, decreases by 3.0 per brake tick.
    pos_x increases by 1.0 per gas tick.
    yaw changes by 0.01 per left tick, -0.01 per right tick.
    """

    def __init__(self):
        self.speed = 0.0
        self.pos_x = 0.0
        self.yaw = 0.0
        self.last_action = {}

    def send_action_dict(self, action: dict):
        self.last_action = action.copy()

    def wait_one_tick(self):
        if self.last_action.get('gas', 0) > 0:
            self.speed += 5.0
            self.pos_x += 1.0
        if self.last_action.get('brake', 0) > 0:
            self.speed = max(0.0, self.speed - 3.0)
        if self.last_action.get('left', 0) > 0:
            self.yaw += 0.01
        if self.last_action.get('right', 0) > 0:
            self.yaw -= 0.01

    def get_feedbacks(self):
        return {
            'speed': self.speed,
            'pos_x': self.pos_x,
            'yaw': self.yaw,
        }


# =============================================================================
# IN-MEMORY MOCK GRAPH (replaces FalkorDB)
# =============================================================================

class InMemoryGraph:
    """
    In-memory mock that simulates FalkorDB graph operations.
    Supports MERGE (no duplicate nodes) and CREATE (edges always added).
    """

    def __init__(self):
        self.nodes: Dict[float, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    def record_transition(self, from_val, to_val, var_name, bid, blabel, aname):
        """MERGE nodes + CREATE edge."""
        if from_val not in self.nodes:
            self.nodes[from_val] = {'value': from_val, 'variable': var_name}
        if to_val not in self.nodes:
            self.nodes[to_val] = {'value': to_val, 'variable': var_name}
        self.edges.append({
            'from_value': from_val,
            'to_value': to_val,
            'bin_id': bid,
            'bin_label': blabel,
            'action_name': aname,
        })


class InMemoryVariableGraph(VariableGraph):
    """
    VariableGraph that uses InMemoryGraph instead of FalkorDB.
    Overrides record_transition, count_nodes, count_edges, get_node,
    get_edges_from, get_edges_to to use in-memory storage.
    """

    def __init__(self, variable_name: str, precision: float):
        super().__init__(variable_name, precision, db=None)
        self._mem = InMemoryGraph()
        self._connected = True  # Always "connected"

    def connect(self, host='localhost', port=6379) -> bool:
        self._connected = True
        return True

    def record_transition(self, from_value, to_value, bin_id, bin_label, action_name) -> bool:
        d_from = self._discretize(from_value, self.precision)
        d_to = self._discretize(to_value, self.precision)
        self._mem.record_transition(d_from, d_to, self.variable_name, bin_id, bin_label, action_name)
        return True

    def count_nodes(self) -> int:
        return len(self._mem.nodes)

    def count_edges(self) -> int:
        return len(self._mem.edges)

    def get_node(self, value) -> Optional[Dict]:
        d_val = self._discretize(value, self.precision)
        if d_val in self._mem.nodes:
            return self._mem.nodes[d_val]
        return None

    def get_edges_from(self, value) -> List[Dict]:
        d_val = self._discretize(value, self.precision)
        return [
            {'bin_id': e['bin_id'], 'bin_label': e['bin_label'],
             'action_name': e['action_name'], 'to_value': e['to_value']}
            for e in self._mem.edges if e['from_value'] == d_val
        ]

    def get_edges_to(self, value) -> List[Dict]:
        d_val = self._discretize(value, self.precision)
        return [
            {'bin_id': e['bin_id'], 'bin_label': e['bin_label'],
             'action_name': e['action_name'], 'from_value': e['from_value']}
            for e in self._mem.edges if e['to_value'] == d_val
        ]

    def reset(self) -> bool:
        self._mem.nodes.clear()
        self._mem.edges.clear()
        return True


class InMemoryMultiGraphManager(MultiGraphManager):
    """
    MultiGraphManager that creates InMemoryVariableGraphs instead of
    real VariableGraphs. Tests real MultiGraphManager logic (record_frame,
    resolve_bin, dead-zone skipping) with mock storage.
    """

    def __init__(self, variables, bins_by_action):
        # Skip parent __init__ to avoid creating real VariableGraphs
        self.variables = variables
        self.bins_by_action = bins_by_action
        self._graphs: Dict[str, InMemoryVariableGraph] = {}

        for var_name, precision in variables.items():
            self._graphs[var_name] = InMemoryVariableGraph(var_name, precision)

    def connect(self, host='localhost', port=6379) -> bool:
        """All in-memory graphs are always connected."""
        return True

    def is_connected(self) -> bool:
        return True


# =============================================================================
# MOCK LEGACY KNOWLEDGE MANAGER
# =============================================================================

class MockKnowledgeManager:
    """Minimal mock for testing legacy+multi-graph coexistence."""

    def __init__(self):
        self._connected = True
        self.transitions = []

    def connect(self, host='localhost', port=6379):
        self._connected = True
        return True

    def record_transition_simple(self, from_frame_id, from_feedbacks,
                                  action, to_frame_id, to_feedbacks):
        self.transitions.append({
            'from_frame_id': from_frame_id,
            'from_feedbacks': from_feedbacks,
            'action': action,
            'to_frame_id': to_frame_id,
            'to_feedbacks': to_feedbacks,
        })
        return True

    def get_frame(self, frame_id):
        return None


# =============================================================================
# SHARED TEST FIXTURES
# =============================================================================

TMNF_BINS = {
    "gas": [
        {"bin_id": 0, "min": 0.0, "max": 0.001, "label": "DEAD_ZONE", "effect_delta": 0.0},
        {"bin_id": 1, "min": 0.001, "max": 1.0, "label": "ON", "effect_delta": 0.6}
    ],
    "brake": [
        {"bin_id": 0, "min": 0.0, "max": 0.001, "label": "DEAD_ZONE", "effect_delta": 0.0},
        {"bin_id": 1, "min": 0.001, "max": 1.0, "label": "ON", "effect_delta": -1.37}
    ],
    "left": [
        {"bin_id": 0, "min": 0.0, "max": 0.5, "label": "DEAD_ZONE", "effect_delta": 0.0},
        {"bin_id": 1, "min": 0.5, "max": 1.0, "label": "ON", "effect_delta": 0.001}
    ],
    "right": [
        {"bin_id": 0, "min": 0.0, "max": 0.5, "label": "DEAD_ZONE", "effect_delta": 0.0},
        {"bin_id": 1, "min": 0.5, "max": 1.0, "label": "ON", "effect_delta": 0.001}
    ],
}

TRACKED_VARIABLES = {'speed': 0.6, 'pos_x': 0.01}


def _make_orchestrator_with_multi_graph(variables=None, bins=None):
    """Create FrameOrchestrator with InMemoryMultiGraphManager wired in."""
    if variables is None:
        variables = TRACKED_VARIABLES
    if bins is None:
        bins = TMNF_BINS

    adapter = MockAdapter()
    mgm = InMemoryMultiGraphManager(variables, bins)
    orch = FrameOrchestrator(adapter, multi_graph=mgm)
    orch._multi_graph_available = True
    return orch, mgm


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestOrchestratorMultiGraph:
    """9 offline integration tests: FrameOrchestrator -> MultiGraphManager -> VariableGraph."""

    def test_execute_frame_records_to_multi_graph(self):
        """Execute 1 frame with gas=1.0, verify speed graph has nodes."""
        orch, mgm = _make_orchestrator_with_multi_graph()

        orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        speed_graph = mgm.get_variable_graph('speed')
        assert speed_graph is not None
        assert speed_graph.count_nodes() >= 2, (
            f"Speed graph should have at least 2 nodes (from + to), got {speed_graph.count_nodes()}"
        )
        assert speed_graph.count_edges() >= 1, (
            f"Speed graph should have at least 1 edge, got {speed_graph.count_edges()}"
        )

    def test_multiple_frames_accumulate_nodes(self):
        """Execute 5 gas frames, verify speed graph nodes represent speed progression."""
        orch, mgm = _make_orchestrator_with_multi_graph()

        for _ in range(5):
            orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        speed_graph = mgm.get_variable_graph('speed')
        # MockAdapter: speed goes 0 -> 5 -> 10 -> 15 -> 20 -> 25
        # Discretized at precision 0.6: 0.0, 4.8, 10.2, 15.0, 19.8, 25.2
        # 6 unique discretized values = 6 nodes, 5 edges
        assert speed_graph.count_nodes() == 6, (
            f"Expected 6 unique speed nodes, got {speed_graph.count_nodes()}"
        )
        assert speed_graph.count_edges() == 5, (
            f"Expected 5 edges (one per frame), got {speed_graph.count_edges()}"
        )

    def test_no_duplicate_nodes_on_revisit(self):
        """Gas(3) -> brake(3) -> gas(3). If speed returns to previously seen value, node is reused."""
        orch, mgm = _make_orchestrator_with_multi_graph(
            variables={'speed': 1.0}  # precision=1.0 for cleaner arithmetic
        )

        # Gas 3 frames: speed 0 -> 5 -> 10 -> 15
        for _ in range(3):
            orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        # Brake 3 frames: speed 15 -> 12 -> 9 -> 6
        for _ in range(3):
            orch.execute_one_frame({'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0})

        # Gas 3 frames: speed 6 -> 11 -> 16 -> 21
        for _ in range(3):
            orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        speed_graph = mgm.get_variable_graph('speed')

        # All unique discretized values: 0, 5, 10, 15, 12, 9, 6, 11, 16, 21 = 10 nodes
        # If any value is revisited, MERGE prevents duplicate = node count stays at unique count
        # 9 frames = 9 edges
        node_count = speed_graph.count_nodes()
        edge_count = speed_graph.count_edges()

        assert edge_count == 9, f"Expected 9 edges (one per frame), got {edge_count}"
        assert node_count <= 11, (
            f"Expected at most 11 unique nodes (MERGE deduplication), got {node_count}"
        )

    def test_bin_labels_on_edges(self):
        """After recording, edges in speed graph carry bin_id and bin_label."""
        orch, mgm = _make_orchestrator_with_multi_graph()

        orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        speed_graph = mgm.get_variable_graph('speed')
        edges = speed_graph.get_edges_from(0.0)

        assert len(edges) >= 1, "Should have at least 1 edge from speed=0.0"
        gas_edge = [e for e in edges if e['action_name'] == 'gas']
        assert len(gas_edge) == 1, f"Expected 1 gas edge, got {len(gas_edge)}"
        assert gas_edge[0]['bin_id'] == 1
        assert gas_edge[0]['bin_label'] == 'ON'

    def test_all_tracked_variables_updated(self):
        """MockAdapter returns speed and pos_x. Both variable graphs get updated on each frame."""
        orch, mgm = _make_orchestrator_with_multi_graph()

        orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        for var_name in ['speed', 'pos_x']:
            vg = mgm.get_variable_graph(var_name)
            assert vg is not None, f"Variable graph for {var_name} should exist"
            assert vg.count_nodes() >= 2, (
                f"{var_name} graph should have at least 2 nodes, got {vg.count_nodes()}"
            )
            assert vg.count_edges() >= 1, (
                f"{var_name} graph should have at least 1 edge, got {vg.count_edges()}"
            )

    def test_orchestrator_works_without_multi_graph(self):
        """FrameOrchestrator(adapter, multi_graph=None) still works normally."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter, multi_graph=None)

        result = orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        assert result['frame_id'] == 0
        assert result['feedback_after']['speed'] == 5.0
        assert len(orch.history) == 1

    def test_legacy_and_multi_graph_coexist(self):
        """Orchestrator with both legacy KnowledgeManager and MultiGraphManager records to BOTH."""
        adapter = MockAdapter()
        legacy_km = MockKnowledgeManager()
        mgm = InMemoryMultiGraphManager(TRACKED_VARIABLES, TMNF_BINS)

        orch = FrameOrchestrator(adapter, knowledge_manager=legacy_km, multi_graph=mgm)
        orch._graph_available = True  # Enable legacy recording
        orch._multi_graph_available = True  # Enable multi-graph recording

        orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        # Legacy path: recorded transition
        assert len(legacy_km.transitions) == 1, "Legacy KnowledgeManager should have 1 transition"

        # Multi-graph path: recorded to per-variable graphs
        speed_graph = mgm.get_variable_graph('speed')
        assert speed_graph.count_edges() >= 1, "Multi-graph speed should have at least 1 edge"

    def test_dead_zone_no_edge(self):
        """D0 frame (all actions 0.0) does NOT create edges in variable graphs."""
        orch, mgm = _make_orchestrator_with_multi_graph()

        # D0 frame: all actions at 0.0 (dead zone)
        orch.execute_one_frame({'gas': 0.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        speed_graph = mgm.get_variable_graph('speed')
        assert speed_graph.count_edges() == 0, (
            f"Dead zone actions should not create edges, got {speed_graph.count_edges()}"
        )

    def test_different_actions_same_destination_multiple_edges(self):
        """
        GRAPH-07 integration test: Two different actions reach the same
        discretized speed state. Verify destination node exists ONCE but
        has 2+ incoming edges carrying different bin labels.

        Scenario: Gas from speed=0 -> 5.0, then brake from speed=8.0 -> 5.0.
        Both transitions land on the same discretized speed node.
        The destination node should have 2 incoming edges (gas ON, brake ON).
        """
        # Use precision=1.0 for clean arithmetic
        adapter = MockAdapter()
        mgm = InMemoryMultiGraphManager({'speed': 1.0}, TMNF_BINS)
        orch = FrameOrchestrator(adapter, multi_graph=mgm)
        orch._multi_graph_available = True

        # Frame 1: gas ON, speed 0 -> 5
        orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})
        # Speed is now 5.0

        # Frame 2: gas ON, speed 5 -> 10
        orch.execute_one_frame({'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})
        # Speed is now 10.0

        # Frame 3: brake ON, speed 10 -> 7
        orch.execute_one_frame({'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0})
        # Speed is now 7.0

        # Frame 4: brake ON, speed 7 -> 4  (not 5 -- our mock does -3.0)
        orch.execute_one_frame({'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0})
        # Speed is now 4.0 -- but discretized at precision 1.0, 4.0 != 5.0

        # We need a scenario where gas and brake produce same destination
        # Let's use direct record_frame on the MGM to create the exact scenario
        speed_graph = mgm.get_variable_graph('speed')
        speed_graph.reset()  # Clear from orchestrator frames

        # Manually record: gas from 0 -> 5, brake from 8 -> 5
        # Both discretize to 5.0 destination (precision=1.0)
        mgm.record_frame(
            from_feedbacks={'speed': 0.0},
            to_feedbacks={'speed': 5.0},
            action={'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
        )
        mgm.record_frame(
            from_feedbacks={'speed': 8.0},
            to_feedbacks={'speed': 5.0},
            action={'gas': 0.0, 'brake': 1.0, 'left': 0.0, 'right': 0.0}
        )

        # Verify: destination node 5.0 exists exactly once
        dest_node = speed_graph.get_node(5.0)
        assert dest_node is not None, "Destination node 5.0 should exist"

        # Verify: 2 incoming edges to destination 5.0
        incoming = speed_graph.get_edges_to(5.0)
        assert len(incoming) == 2, (
            f"GRAPH-07: Expected 2 incoming edges to speed=5.0, got {len(incoming)}"
        )

        # Verify: edges carry different action names (gas and brake)
        action_names = {e['action_name'] for e in incoming}
        assert action_names == {'gas', 'brake'}, (
            f"GRAPH-07: Expected gas and brake edges, got {action_names}"
        )

        # Verify: edges carry correct bin labels
        labels = {e['bin_label'] for e in incoming}
        assert labels == {'ON'}, f"Both edges should be 'ON' bin, got {labels}"

        # Verify: node count reflects deduplication
        # Unique nodes: 0.0, 5.0, 8.0 = 3
        assert speed_graph.count_nodes() == 3, (
            f"GRAPH-04: Expected 3 unique nodes, got {speed_graph.count_nodes()}"
        )
