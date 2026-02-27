"""
VARIABLE GRAPH - Per-Variable Knowledge Graph

Sutton Jan 15: "the minimum is 0.1... every 0.1 becomes one node
because that's the bin"

Sutton Jan 24: "is the duplication of nodes allowed or not? No not at all"

Each feedback variable (speed, pos_x, yaw, etc.) gets its own FalkorDB
graph. Nodes represent discretized state values. Edges represent action
bins that caused transitions between those values.

Graph Structure:
    Nodes: (:State {value: <discretized>, variable: <name>})
    Edges: -[:ACTION_BIN {bin_id, bin_label, action_name}]->

Key semantics:
    - MERGE on value prevents duplicate nodes (GRAPH-04)
    - CREATE for edges allows repeated transitions (valid data)
    - Discretization uses system precision (min_delta from bin discovery)
"""

import logging
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class VariableGraph:
    """
    Single-variable knowledge graph with discretized state nodes
    and bin-labeled action edges.

    One instance per feedback variable. Each manages its own
    FalkorDB graph named 'kg_{variable_name}'.
    """

    def __init__(self, variable_name: str, precision: float, db=None):
        """
        Initialize a per-variable knowledge graph.

        Args:
            variable_name: Feedback variable name (e.g. 'speed', 'pos_x', 'yaw')
            precision: Minimum delta from bin discovery, used as discretization
                       resolution. E.g. 0.6 means values are rounded to nearest
                       multiple of 0.6.
            db: FalkorDB instance. If None, graph operations are no-ops
                returning False.
        """
        self.variable_name = variable_name
        self.precision = precision
        self.db = db
        self.graph = None
        self._connected = False
        self._graph_name = f"kg_{variable_name}"

    @staticmethod
    def _discretize(value: float, min_delta: float, precision: int = 7) -> float:
        """Round a state value to the knowledge graph resolution.

        Same math as KnowledgeManager.round_to_resolution but standalone.
        No instance state needed -- pure math.

        Args:
            value: Raw state value
            min_delta: Minimum action effect (graph interval size)
            precision: Decimal precision for final rounding

        Returns:
            Discretized value
        """
        if min_delta > 0:
            value = round(value / min_delta) * min_delta
        return round(value, precision)

    def connect(self, host: str = 'localhost', port: int = 6379) -> bool:
        """
        Select the named graph from FalkorDB.

        Args:
            host: FalkorDB host
            port: FalkorDB port

        Returns:
            True if connected successfully
        """
        try:
            if self.db is None:
                from falkordb import FalkorDB
                self.db = FalkorDB(host=host, port=port)

            self.graph = self.db.select_graph(self._graph_name)
            self._connected = True
            logger.info(f"[VARIABLE_GRAPH] Connected to graph: {self._graph_name}")
            return True

        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] Connection failed for {self._graph_name}: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Check if connected to FalkorDB graph."""
        return self._connected

    def record_transition(
        self,
        from_value: float,
        to_value: float,
        bin_id: int,
        bin_label: str,
        action_name: str
    ) -> bool:
        """
        Record a state transition: discretize values, MERGE nodes, CREATE edge.

        MERGE on value prevents duplicate State nodes (GRAPH-04).
        CREATE for edge allows repeated transitions (same action bin
        between same states in different frames is valid repeat data).

        Args:
            from_value: Raw state value before action
            to_value: Raw state value after action
            bin_id: Integer bin identifier from Phase A
            bin_label: Human-readable label (e.g. 'ON', 'DEAD_ZONE')
            action_name: Which action caused this (e.g. 'gas', 'brake')

        Returns:
            True if recorded successfully
        """
        if not self._connected:
            logger.error(f"[VARIABLE_GRAPH] Cannot record - {self._graph_name} not connected")
            return False

        try:
            d_from = self._discretize(from_value, self.precision)
            d_to = self._discretize(to_value, self.precision)

            # MERGE nodes (no duplicates)
            # CREATE edge (repeated transitions are valid)
            query = (
                "MERGE (from:State {value: $from_val}) "
                "ON CREATE SET from.variable = $var_name "
                "MERGE (to:State {value: $to_val}) "
                "ON CREATE SET to.variable = $var_name "
                "CREATE (from)-[:ACTION_BIN {"
                "bin_id: $bid, bin_label: $blabel, action_name: $aname"
                "}]->(to)"
            )

            params = {
                'from_val': d_from,
                'to_val': d_to,
                'var_name': self.variable_name,
                'bid': bin_id,
                'blabel': bin_label,
                'aname': action_name,
            }

            self.graph.query(query, params)

            logger.debug(
                f"[VARIABLE_GRAPH] {self._graph_name}: "
                f"{d_from} --[{action_name}:{bin_label}]--> {d_to}"
            )
            return True

        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] record_transition failed: {e}")
            return False

    def get_node(self, value: float) -> Optional[Dict[str, Any]]:
        """
        Get a State node by its discretized value.

        Args:
            value: Raw state value (will be discretized)

        Returns:
            Node properties dict or None if not found
        """
        if not self._connected:
            return None

        try:
            d_value = self._discretize(value, self.precision)
            query = "MATCH (s:State {value: $val}) RETURN s.value, s.variable"
            result = self.graph.query(query, {'val': d_value})

            if not result.result_set:
                return None

            row = result.result_set[0]
            return {'value': row[0], 'variable': row[1]}

        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] get_node failed: {e}")
            return None

    def get_edges_from(self, value: float) -> List[Dict[str, Any]]:
        """
        Get all outgoing ACTION_BIN edges from a discretized node.

        Args:
            value: Raw state value (will be discretized)

        Returns:
            List of edge property dicts
        """
        if not self._connected:
            return []

        try:
            d_value = self._discretize(value, self.precision)
            query = (
                "MATCH (from:State {value: $val})-[e:ACTION_BIN]->(to:State) "
                "RETURN e.bin_id, e.bin_label, e.action_name, to.value"
            )
            result = self.graph.query(query, {'val': d_value})

            edges = []
            for row in result.result_set:
                edges.append({
                    'bin_id': row[0],
                    'bin_label': row[1],
                    'action_name': row[2],
                    'to_value': row[3],
                })
            return edges

        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] get_edges_from failed: {e}")
            return []

    def get_edges_to(self, value: float) -> List[Dict[str, Any]]:
        """
        Get all incoming ACTION_BIN edges to a discretized node.

        Args:
            value: Raw state value (will be discretized)

        Returns:
            List of edge property dicts
        """
        if not self._connected:
            return []

        try:
            d_value = self._discretize(value, self.precision)
            query = (
                "MATCH (from:State)-[e:ACTION_BIN]->(to:State {value: $val}) "
                "RETURN e.bin_id, e.bin_label, e.action_name, from.value"
            )
            result = self.graph.query(query, {'val': d_value})

            edges = []
            for row in result.result_set:
                edges.append({
                    'bin_id': row[0],
                    'bin_label': row[1],
                    'action_name': row[2],
                    'from_value': row[3],
                })
            return edges

        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] get_edges_to failed: {e}")
            return []

    def count_nodes(self) -> int:
        """Count State nodes in this graph."""
        if not self._connected:
            return 0

        try:
            result = self.graph.query("MATCH (s:State) RETURN count(s)")
            return result.result_set[0][0]
        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] count_nodes failed: {e}")
            return 0

    def count_edges(self) -> int:
        """Count ACTION_BIN edges in this graph."""
        if not self._connected:
            return 0

        try:
            result = self.graph.query("MATCH ()-[e:ACTION_BIN]->() RETURN count(e)")
            return result.result_set[0][0]
        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] count_edges failed: {e}")
            return 0

    def reset(self) -> bool:
        """Delete all nodes and edges in this graph."""
        if not self._connected:
            logger.error(f"[VARIABLE_GRAPH] Cannot reset - {self._graph_name} not connected")
            return False

        try:
            self.graph.query("MATCH (n) DETACH DELETE n")
            logger.info(f"[VARIABLE_GRAPH] {self._graph_name} reset complete")
            return True
        except Exception as e:
            logger.error(f"[VARIABLE_GRAPH] reset failed: {e}")
            return False
