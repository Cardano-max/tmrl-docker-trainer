"""
MULTI GRAPH MANAGER - Coordinates Per-Variable Knowledge Graphs

Sutton Jan 15: "Every 0.1 becomes one node because that's the bin"
Sutton Jan 24: "the system should have all the graphs already populated"

Records one frame of experience across ALL per-variable graphs
simultaneously. Each feedback variable (speed, pos_x, yaw, etc.)
has its own VariableGraph. When a frame is recorded, all graphs
update at once.

Usage:
    mgm = MultiGraphManager(
        variables={'speed': 0.6, 'pos_x': 0.001},
        bins_by_action={
            'gas': [{'bin_id': 0, 'min': 0.0, 'max': 0.001, 'label': 'DEAD_ZONE', 'effect_delta': 0.0},
                    {'bin_id': 1, 'min': 0.001, 'max': 1.0, 'label': 'ON', 'effect_delta': 0.6}],
        }
    )
    mgm.connect()
    mgm.record_frame(
        from_feedbacks={'speed': 10.0, 'pos_x': 50.0},
        to_feedbacks={'speed': 10.6, 'pos_x': 50.1},
        action={'gas': 1.0, 'brake': 0.0}
    )
"""

import logging
from typing import Dict, Optional, List, Any

from knowledge.variable_graph import VariableGraph

logger = logging.getLogger(__name__)


class MultiGraphManager:
    """
    Coordinates multiple VariableGraph instances for simultaneous
    per-frame recording across all feedback variables.

    Creates one VariableGraph per variable. On each frame,
    record_frame() updates all graphs simultaneously.
    """

    def __init__(
        self,
        variables: Dict[str, float],
        bins_by_action: Dict[str, list]
    ):
        """
        Initialize multi-graph manager.

        Args:
            variables: Mapping of variable_name -> precision.
                       E.g. {'speed': 0.6, 'pos_x': 0.001, 'yaw': 0.001}
                       Precision = min_delta from bin discovery.

            bins_by_action: Mapping of action_name -> list of bin dicts.
                           Each bin dict has keys: bin_id, min, max, label,
                           and optionally effect_delta or effect_mean.

                           CRITICAL: This expects dict format with keys
                           'min' and 'max' (NOT 'a_min'/'a_max'). This is
                           the format produced by ActionBin.to_dict() from
                           intelligence_experimentation.py. If ActionBin
                           dataclass objects are passed instead of dicts,
                           convert them first via:
                               [b.to_dict() for b in bins]

                           Canonical bin dict format:
                               {'bin_id': 0, 'min': 0.0, 'max': 0.001,
                                'label': 'DEAD_ZONE', 'effect_delta': 0.0}
        """
        self.variables = variables
        self.bins_by_action = bins_by_action
        self._graphs: Dict[str, VariableGraph] = {}

        # Create one VariableGraph per variable
        for var_name, precision in variables.items():
            self._graphs[var_name] = VariableGraph(var_name, precision)

        logger.info(
            f"[MULTI_GRAPH] Created {len(self._graphs)} variable graphs: "
            f"{list(self._graphs.keys())}"
        )

    def connect(self, host: str = 'localhost', port: int = 6379) -> bool:
        """
        Connect all VariableGraph instances to FalkorDB.

        Returns True only if ALL graphs connect successfully.

        Args:
            host: FalkorDB host
            port: FalkorDB port

        Returns:
            True if all connected
        """
        all_ok = True
        for var_name, vg in self._graphs.items():
            if not vg.connect(host, port):
                logger.error(f"[MULTI_GRAPH] Failed to connect graph: {var_name}")
                all_ok = False

        if all_ok:
            logger.info(f"[MULTI_GRAPH] All {len(self._graphs)} graphs connected")
        return all_ok

    def is_connected(self) -> bool:
        """True if all graphs are connected."""
        if not self._graphs:
            return False
        return all(vg.is_connected() for vg in self._graphs.values())

    def resolve_bin(
        self, action_name: str, value: float
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a raw action value to its discovered bin.

        Finds which bin contains the given value based on [min, max) ranges.
        Falls back to last bin (saturation) if value exceeds all ranges.

        Uses dict keys 'min' and 'max' for bin boundaries (ActionBin.to_dict()
        format).

        Args:
            action_name: e.g. 'gas', 'brake', 'left', 'right'
            value: Raw action value

        Returns:
            Bin dict or None if no bins defined for this action
        """
        bins = self.bins_by_action.get(action_name, [])
        for b in bins:
            if b['min'] <= value < b['max']:
                return b
        # Fallback: last bin (saturation)
        if bins:
            return bins[-1]
        return None

    def record_frame(
        self,
        from_feedbacks: Dict[str, float],
        to_feedbacks: Dict[str, float],
        action: Dict[str, float]
    ) -> bool:
        """
        Record one frame of experience across ALL per-variable graphs.

        For each variable in self.variables:
            - Extract from_value and to_value from feedbacks
            - For each action, resolve to bin
            - Record transition in the variable's graph

        This implements GRAPH-06 (all graphs update simultaneously) and
        GRAPH-10 (one node per graph with action edge).

        Skips variables not present in feedbacks (graceful).
        Skips dead-zone actions (bin_id=0 with value 0.0) -- D0 is a real
        action but the dead-zone bin doesn't create meaningful transitions.

        Args:
            from_feedbacks: Feedback values before action (e.g. {'speed': 10.0, 'pos_x': 50.0})
            to_feedbacks: Feedback values after action
            action: Action taken (e.g. {'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        Returns:
            True if at least one transition was recorded
        """
        any_recorded = False

        for var_name, vg in self._graphs.items():
            # Skip variables not in feedbacks
            if var_name not in from_feedbacks or var_name not in to_feedbacks:
                continue

            from_value = from_feedbacks[var_name]
            to_value = to_feedbacks[var_name]

            # For each action, resolve bin and record transition
            for action_name, action_value in action.items():
                resolved = self.resolve_bin(action_name, action_value)
                if resolved is None:
                    continue

                # Skip dead-zone (bin_id=0 with zero value)
                if resolved.get('bin_id', -1) == 0 and abs(action_value) < 1e-8:
                    continue

                success = vg.record_transition(
                    from_value=from_value,
                    to_value=to_value,
                    bin_id=resolved['bin_id'],
                    bin_label=resolved['label'],
                    action_name=action_name
                )
                if success:
                    any_recorded = True

        return any_recorded

    def get_variable_graph(self, variable_name: str) -> Optional[VariableGraph]:
        """
        Return specific VariableGraph for direct queries.

        Args:
            variable_name: Variable name (e.g. 'speed')

        Returns:
            VariableGraph instance or None
        """
        return self._graphs.get(variable_name)

    def get_all_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Return node/edge counts per variable.

        Returns:
            Dict mapping variable name to {'nodes': N, 'edges': M}
        """
        stats = {}
        for var_name, vg in self._graphs.items():
            stats[var_name] = {
                'nodes': vg.count_nodes(),
                'edges': vg.count_edges(),
            }
        return stats

    def reset_all(self) -> bool:
        """
        Reset all variable graphs (delete all nodes and edges).

        Returns:
            True if all resets succeeded
        """
        all_ok = True
        for var_name, vg in self._graphs.items():
            if not vg.reset():
                logger.error(f"[MULTI_GRAPH] Failed to reset graph: {var_name}")
                all_ok = False
        return all_ok
