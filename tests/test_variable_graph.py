"""
Offline Tests for VariableGraph and MultiGraphManager

Tests run WITHOUT FalkorDB -- uses MockFalkorGraph that simulates
MERGE/CREATE/MATCH Cypher semantics in-memory.

Validates:
- GRAPH-03: Discretization uses system precision
- GRAPH-04: No duplicate nodes (MERGE semantics)
- GRAPH-06: All graphs update simultaneously
- GRAPH-07: Same node reachable via different actions
- GRAPH-08: Bin-labeled edges
"""

import pytest
import re
from typing import Any, Dict, List, Optional


# =============================================================================
# MOCK FALKORDB
# =============================================================================

class MockResultSet:
    """Mock FalkorDB result set."""

    def __init__(self, rows: List[list]):
        self.result_set = rows


class MockFalkorGraph:
    """
    In-memory mock that simulates FalkorDB Cypher operations.

    Supports:
    - MERGE (s:State {value: $val}) ON CREATE SET ... -- upsert nodes
    - CREATE (from)-[:ACTION_BIN {...}]->(to) -- create edges
    - MATCH (s:State {value: $val}) RETURN ... -- query nodes
    - MATCH ()-[e:ACTION_BIN]->() -- query edges
    - MATCH (n) DETACH DELETE n -- reset
    - MATCH (s:State) RETURN count(s) -- count nodes
    - MATCH ()-[e:ACTION_BIN]->() RETURN count(e) -- count edges
    """

    def __init__(self):
        # nodes: {discretized_value: {value: X, variable: Y}}
        self.nodes: Dict[float, Dict[str, Any]] = {}
        # edges: list of {from_value, to_value, bin_id, bin_label, action_name}
        self.edges: List[Dict[str, Any]] = []

    def query(self, cypher: str, params: dict = None) -> MockResultSet:
        """Parse and execute simplified Cypher queries."""
        if params is None:
            params = {}

        # Substitute parameters
        resolved = cypher
        for k, v in params.items():
            if isinstance(v, str):
                resolved = resolved.replace(f"${k}", f"'{v}'")
            else:
                resolved = resolved.replace(f"${k}", str(v))

        # DETACH DELETE -- reset
        if 'DETACH DELETE' in resolved:
            self.nodes.clear()
            self.edges.clear()
            return MockResultSet([])

        # Count nodes
        if 'count(s)' in resolved and 'State' in resolved:
            return MockResultSet([[len(self.nodes)]])

        # Count edges
        if 'count(e)' in resolved and 'ACTION_BIN' in resolved:
            return MockResultSet([[len(self.edges)]])

        # MERGE + CREATE (record_transition pattern)
        if 'MERGE' in resolved and 'CREATE' in resolved:
            return self._handle_merge_create(resolved, params)

        # MATCH node by value and return properties
        if 'MATCH' in resolved and 'RETURN' in resolved and 'ACTION_BIN' not in resolved:
            return self._handle_match_node(resolved, params)

        # MATCH edges from a node
        if 'MATCH' in resolved and 'ACTION_BIN' in resolved and 'RETURN' in resolved:
            return self._handle_match_edges(resolved, params)

        return MockResultSet([])

    def _handle_merge_create(self, cypher: str, params: dict) -> MockResultSet:
        """Handle MERGE nodes + CREATE edge pattern."""
        # Extract from_val and to_val from params
        from_val = params.get('from_val')
        to_val = params.get('to_val')
        var_name = params.get('var_name', '')
        bid = params.get('bid', 0)
        blabel = params.get('blabel', '')
        aname = params.get('aname', '')

        # MERGE: create node only if not exists
        if from_val is not None and from_val not in self.nodes:
            self.nodes[from_val] = {'value': from_val, 'variable': var_name}
        if to_val is not None and to_val not in self.nodes:
            self.nodes[to_val] = {'value': to_val, 'variable': var_name}

        # CREATE edge
        if from_val is not None and to_val is not None:
            self.edges.append({
                'from_value': from_val,
                'to_value': to_val,
                'bin_id': bid,
                'bin_label': blabel,
                'action_name': aname,
            })

        return MockResultSet([])

    def _handle_match_node(self, cypher: str, params: dict) -> MockResultSet:
        """Handle MATCH (s:State {value: $val}) RETURN s.value, s.variable"""
        val = params.get('val')
        if val is not None and val in self.nodes:
            node = self.nodes[val]
            return MockResultSet([[node['value'], node.get('variable', '')]])
        return MockResultSet([])

    def _handle_match_edges(self, cypher: str, params: dict) -> MockResultSet:
        """Handle MATCH edge queries."""
        val = params.get('val')
        rows = []

        # Determine direction by checking which alias has {value: $val}
        # get_edges_from: (from:State {value: $val})-[e:ACTION_BIN]->(to:State)
        # get_edges_to:   (from:State)-[e:ACTION_BIN]->(to:State {value: $val})
        compact = cypher.replace(' ', '')

        if 'from:State{value:' in compact:
            # $val is on the FROM side -- edges FROM this node
            for e in self.edges:
                if e['from_value'] == val:
                    rows.append([
                        e['bin_id'],
                        e['bin_label'],
                        e['action_name'],
                        e['to_value'],
                    ])
        elif 'to:State{value:' in compact:
            # $val is on the TO side -- edges TO this node
            for e in self.edges:
                if e['to_value'] == val:
                    rows.append([
                        e['bin_id'],
                        e['bin_label'],
                        e['action_name'],
                        e['from_value'],
                    ])

        return MockResultSet(rows)


def _make_connected_vg(variable_name: str = 'speed', precision: float = 0.6):
    """Create a VariableGraph with mock graph injected."""
    from knowledge.variable_graph import VariableGraph
    vg = VariableGraph(variable_name, precision)
    vg.graph = MockFalkorGraph()
    vg._connected = True
    return vg


# =============================================================================
# TestVariableGraph
# =============================================================================

class TestVariableGraph:
    """Tests for VariableGraph class."""

    def test_discretize_rounds_to_precision(self):
        """Value 5.23 with precision 0.6 rounds to 5.4 (nearest multiple of 0.6)."""
        from knowledge.variable_graph import VariableGraph
        # 5.23 / 0.6 = 8.7167, round = 9, 9 * 0.6 = 5.4
        result = VariableGraph._discretize(5.23, 0.6)
        assert result == 5.4, f"Expected 5.4, got {result}"

    def test_discretize_exact_multiple(self):
        """Value that is already a multiple of precision stays unchanged."""
        from knowledge.variable_graph import VariableGraph
        result = VariableGraph._discretize(3.0, 0.6)
        assert result == 3.0, f"Expected 3.0, got {result}"

    def test_discretize_zero_min_delta(self):
        """min_delta=0 skips rounding, just applies precision truncation."""
        from knowledge.variable_graph import VariableGraph
        result = VariableGraph._discretize(5.123456789, 0.0)
        assert result == 5.1234568, f"Expected 5.1234568, got {result}"

    def test_merge_prevents_duplicate_nodes(self):
        """Record two transitions to same discretized value, count_nodes returns unique count."""
        vg = _make_connected_vg('speed', 0.6)

        # Transition 1: 0.0 -> 5.4 via gas ON
        vg.record_transition(0.0, 5.23, 1, 'ON', 'gas')  # 5.23 -> 5.4

        # Transition 2: 10.0 -> 5.4 via brake ON (same destination)
        vg.record_transition(10.0, 5.5, 1, 'ON', 'brake')  # 5.5 -> 5.4

        # Should be 3 unique nodes: 0.0, 5.4, 10.2 (10.0 discretized)
        # Wait: 10.0 / 0.6 = 16.667, round = 17, 17 * 0.6 = 10.2
        # So nodes: 0.0, 5.4, 10.2 = 3 unique nodes
        assert vg.count_nodes() == 3, f"Expected 3 unique nodes, got {vg.count_nodes()}"

    def test_graph04_no_duplicate_critical(self):
        """
        GRAPH-04: Recording transitions with same discretized destination
        from different sources results in ONE node for that value.

        Transition 1: 10.0 -> 15.0 (gas ON)
        Transition 2: 10.0 -> 15.0 (gas ON, same frame repeated)
        Transition 3: 20.0 -> 15.0 (brake ON, different source, same dest)

        Result: value=15.0 should be EXACTLY ONE node, not three.
        """
        vg = _make_connected_vg('speed', 1.0)  # precision=1.0 for clean values

        # Three transitions all targeting 15.0
        vg.record_transition(10.0, 15.0, 1, 'ON', 'gas')
        vg.record_transition(10.0, 15.0, 1, 'ON', 'gas')   # repeat
        vg.record_transition(20.0, 15.0, 1, 'ON', 'brake')  # different source

        # Unique nodes: 10.0, 15.0, 20.0 = 3 (NOT 5 or 7)
        assert vg.count_nodes() == 3, (
            f"GRAPH-04 violated: Expected 3 unique nodes, got {vg.count_nodes()}"
        )

        # But edges: 3 (each transition creates one edge)
        assert vg.count_edges() == 3

    def test_different_values_create_different_nodes(self):
        """Two distinct discretized values = two nodes."""
        vg = _make_connected_vg('speed', 1.0)

        vg.record_transition(5.0, 10.0, 1, 'ON', 'gas')

        assert vg.count_nodes() == 2

    def test_edge_carries_bin_label(self):
        """After record_transition, edge has bin_id, bin_label, action_name."""
        vg = _make_connected_vg('speed', 1.0)

        vg.record_transition(10.0, 15.0, 1, 'ON', 'gas')

        edges = vg.get_edges_from(10.0)
        assert len(edges) == 1
        edge = edges[0]
        assert edge['bin_id'] == 1
        assert edge['bin_label'] == 'ON'
        assert edge['action_name'] == 'gas'
        assert edge['to_value'] == 15.0

    def test_multiple_edges_same_nodes(self):
        """
        GRAPH-07: Same from/to but different action bins = multiple edges.
        Same node reachable via different actions.
        """
        vg = _make_connected_vg('speed', 1.0)

        # Same from/to, different actions
        vg.record_transition(10.0, 15.0, 1, 'ON', 'gas')
        vg.record_transition(10.0, 15.0, 1, 'ON', 'left')

        assert vg.count_nodes() == 2  # Only 2 unique nodes
        assert vg.count_edges() == 2  # But 2 edges

        edges = vg.get_edges_from(10.0)
        assert len(edges) == 2
        action_names = {e['action_name'] for e in edges}
        assert action_names == {'gas', 'left'}

    def test_no_connection_returns_false(self):
        """Operations return False/empty when not connected."""
        from knowledge.variable_graph import VariableGraph
        vg = VariableGraph('speed', 0.6)  # NOT connected

        assert vg.record_transition(1.0, 2.0, 1, 'ON', 'gas') is False
        assert vg.get_node(1.0) is None
        assert vg.get_edges_from(1.0) == []
        assert vg.get_edges_to(1.0) == []
        assert vg.count_nodes() == 0
        assert vg.count_edges() == 0
        assert vg.reset() is False
        assert vg.is_connected() is False

    def test_get_node_returns_properties(self):
        """get_node returns value and variable for existing node."""
        vg = _make_connected_vg('yaw', 0.001)

        vg.record_transition(1.234, 1.567, 1, 'ON', 'left')

        node = vg.get_node(1.234)
        assert node is not None
        assert node['value'] == vg._discretize(1.234, 0.001)
        assert node['variable'] == 'yaw'

    def test_get_node_nonexistent(self):
        """get_node returns None for non-existent value."""
        vg = _make_connected_vg('speed', 1.0)
        assert vg.get_node(999.0) is None

    def test_get_edges_to(self):
        """get_edges_to returns incoming edges."""
        vg = _make_connected_vg('speed', 1.0)

        vg.record_transition(10.0, 15.0, 1, 'ON', 'gas')
        vg.record_transition(20.0, 15.0, 1, 'ON', 'brake')

        edges = vg.get_edges_to(15.0)
        assert len(edges) == 2
        from_values = {e['from_value'] for e in edges}
        assert from_values == {10.0, 20.0}

    def test_reset_clears_graph(self):
        """reset() removes all nodes and edges."""
        vg = _make_connected_vg('speed', 1.0)

        vg.record_transition(10.0, 15.0, 1, 'ON', 'gas')
        assert vg.count_nodes() == 2
        assert vg.count_edges() == 1

        vg.reset()
        assert vg.count_nodes() == 0
        assert vg.count_edges() == 0

    def test_graph_name(self):
        """Graph name follows kg_{variable_name} pattern."""
        from knowledge.variable_graph import VariableGraph
        vg = VariableGraph('pos_x', 0.001)
        assert vg._graph_name == 'kg_pos_x'


# =============================================================================
# TestMultiGraphManager
# =============================================================================

class TestMultiGraphManager:
    """Tests for MultiGraphManager class."""

    def _make_mgm(self, variables=None, bins_by_action=None):
        """Create MultiGraphManager with mock graphs injected."""
        from knowledge.multi_graph_manager import MultiGraphManager

        if variables is None:
            variables = {'speed': 0.6, 'pos_x': 0.001, 'yaw': 0.001}
        if bins_by_action is None:
            bins_by_action = {
                'gas': [
                    {'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE', 'effect_delta': 0.0},
                    {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON', 'effect_delta': 0.6},
                ],
                'brake': [
                    {'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE', 'effect_delta': 0.0},
                    {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON', 'effect_delta': 0.3},
                ],
                'left': [
                    {'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE', 'effect_delta': 0.0},
                    {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON', 'effect_delta': 0.01},
                ],
                'right': [
                    {'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE', 'effect_delta': 0.0},
                    {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON', 'effect_delta': 0.01},
                ],
            }

        mgm = MultiGraphManager(variables, bins_by_action)

        # Inject mock graphs
        for var_name in mgm._graphs:
            mgm._graphs[var_name].graph = MockFalkorGraph()
            mgm._graphs[var_name]._connected = True

        return mgm

    def test_creates_graph_per_variable(self):
        """MultiGraphManager with 3 variables creates 3 VariableGraph instances."""
        mgm = self._make_mgm()
        assert len(mgm._graphs) == 3
        assert set(mgm._graphs.keys()) == {'speed', 'pos_x', 'yaw'}

    def test_record_frame_updates_all_graphs(self):
        """record_frame with 3 variables records transitions in all 3 graphs."""
        mgm = self._make_mgm()

        result = mgm.record_frame(
            from_feedbacks={'speed': 10.0, 'pos_x': 50.0, 'yaw': 0.5},
            to_feedbacks={'speed': 10.6, 'pos_x': 50.1, 'yaw': 0.51},
            action={'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
        )

        assert result is True

        # Each variable graph should have recorded the transition
        for var_name in ['speed', 'pos_x', 'yaw']:
            vg = mgm.get_variable_graph(var_name)
            assert vg is not None
            assert vg.count_nodes() >= 2, (
                f"Variable {var_name} should have at least 2 nodes"
            )
            assert vg.count_edges() >= 1, (
                f"Variable {var_name} should have at least 1 edge"
            )

    def test_resolve_bin_finds_correct_bin(self):
        """Gas value 0.5 resolves to bin_id=1 (ON)."""
        mgm = self._make_mgm()

        resolved = mgm.resolve_bin('gas', 0.5)
        assert resolved is not None
        assert resolved['bin_id'] == 1
        assert resolved['label'] == 'ON'

    def test_resolve_bin_dead_zone(self):
        """Gas value 0.0 resolves to bin_id=0 (DEAD_ZONE)."""
        mgm = self._make_mgm()

        resolved = mgm.resolve_bin('gas', 0.0)
        assert resolved is not None
        assert resolved['bin_id'] == 0
        assert resolved['label'] == 'DEAD_ZONE'

    def test_dead_zone_action_skipped(self):
        """Gas value 0.0 (dead zone, bin_id=0) does not create edge."""
        mgm = self._make_mgm(variables={'speed': 1.0})

        mgm.record_frame(
            from_feedbacks={'speed': 10.0},
            to_feedbacks={'speed': 10.0},
            action={'gas': 0.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
        )

        vg = mgm.get_variable_graph('speed')
        assert vg.count_edges() == 0, "Dead zone actions should not create edges"

    def test_get_all_stats_returns_per_variable(self):
        """Stats dict has entry per variable."""
        mgm = self._make_mgm()

        mgm.record_frame(
            from_feedbacks={'speed': 10.0, 'pos_x': 50.0, 'yaw': 0.5},
            to_feedbacks={'speed': 10.6, 'pos_x': 50.1, 'yaw': 0.51},
            action={'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
        )

        stats = mgm.get_all_stats()
        assert set(stats.keys()) == {'speed', 'pos_x', 'yaw'}
        for var_name, var_stats in stats.items():
            assert 'nodes' in var_stats
            assert 'edges' in var_stats

    def test_missing_variable_in_feedbacks_skipped(self):
        """Variables not present in feedbacks are skipped gracefully."""
        mgm = self._make_mgm(variables={'speed': 1.0, 'altitude': 0.1})

        # Only provide speed, not altitude
        result = mgm.record_frame(
            from_feedbacks={'speed': 10.0},
            to_feedbacks={'speed': 15.0},
            action={'gas': 1.0}
        )

        assert result is True
        # Speed should have nodes, altitude should have nothing
        assert mgm.get_variable_graph('speed').count_nodes() >= 2
        assert mgm.get_variable_graph('altitude').count_nodes() == 0

    def test_multiple_active_actions_create_multiple_edges(self):
        """When gas AND left are active, each creates an edge per variable."""
        mgm = self._make_mgm(variables={'speed': 1.0})

        mgm.record_frame(
            from_feedbacks={'speed': 10.0},
            to_feedbacks={'speed': 15.0},
            action={'gas': 1.0, 'left': 1.0, 'brake': 0.0, 'right': 0.0}
        )

        vg = mgm.get_variable_graph('speed')
        # gas=1.0 creates 1 edge, left=1.0 creates 1 edge
        # brake=0.0 and right=0.0 are dead zone, skipped
        assert vg.count_edges() == 2
        assert vg.count_nodes() == 2  # Only 2 unique nodes despite 2 edges

    def test_reset_all(self):
        """reset_all clears all variable graphs."""
        mgm = self._make_mgm()

        mgm.record_frame(
            from_feedbacks={'speed': 10.0, 'pos_x': 50.0, 'yaw': 0.5},
            to_feedbacks={'speed': 15.0, 'pos_x': 55.0, 'yaw': 1.0},
            action={'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0}
        )

        mgm.reset_all()

        stats = mgm.get_all_stats()
        for var_name, var_stats in stats.items():
            assert var_stats['nodes'] == 0
            assert var_stats['edges'] == 0

    def test_resolve_bin_saturation_fallback(self):
        """Value exceeding all bin ranges falls back to last bin."""
        mgm = self._make_mgm()

        # Value 5.0 exceeds max of last bin (1.0)
        resolved = mgm.resolve_bin('gas', 5.0)
        assert resolved is not None
        assert resolved['bin_id'] == 1  # Falls back to last bin

    def test_resolve_bin_no_bins(self):
        """Action with no bins returns None."""
        mgm = self._make_mgm(
            variables={'speed': 1.0},
            bins_by_action={'gas': []}
        )
        assert mgm.resolve_bin('gas', 0.5) is None

    def test_is_connected(self):
        """is_connected returns True when all graphs are connected."""
        mgm = self._make_mgm()
        assert mgm.is_connected() is True

    def test_get_variable_graph_nonexistent(self):
        """get_variable_graph returns None for unknown variable."""
        mgm = self._make_mgm()
        assert mgm.get_variable_graph('nonexistent') is None
