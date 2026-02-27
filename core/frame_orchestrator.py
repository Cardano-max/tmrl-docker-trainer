"""
FRAME ORCHESTRATOR - Sutton's 6 Micro-Processes (Jan 9 Meeting)

"instead of creating exploration, let's create small pieces.
Then we're just going to use the small pieces to create intelligence"
    -- Dr. Sutton, Jan 9

6 Micro-Processes per frame:
  1. Send action to environment
  2. Perform action (environment executes for one frame)
  3. Record action
  4. Receive feedback from environment
  5. Collect feedback (all state variables)
  6. Record feedback (store in graph as node)

This is CAPACITY, not intelligence. Intelligence modules compose these operations.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FrameOrchestrator:
    """
    Sutton's 6 micro-processes (Jan 9) -- one atomic operation per frame.

    1. Send action to environment
    2. Perform action (environment executes for one frame)
    3. Record action
    4. Receive feedback from environment
    5. Collect feedback (all state variables)
    6. Record feedback (store in graph as node)

    Generic: works with any adapter that provides:
      - send_action_dict(action)
      - wait_one_tick()
      - get_feedbacks() -> Dict
    """

    def __init__(self, adapter, knowledge_manager=None):
        """
        Initialize frame orchestrator.

        Args:
            adapter: Any adapter with send_action_dict(), wait_one_tick(), get_feedbacks()
            knowledge_manager: Optional KnowledgeManager for graph recording
        """
        self.adapter = adapter
        self.knowledge = knowledge_manager
        self.frame_id = 0
        self.history = []  # In-memory frame history
        self._graph_available = False  # Set by initialize_graph()

    def execute_one_frame(self, action: Dict) -> Dict:
        """
        Execute all 6 micro-processes atomically for one frame.

        Args:
            action: Action dict (e.g. {'gas': 1.0, 'brake': 0.0, 'left': 0.0, 'right': 0.0})

        Returns:
            Dict with frame_id, action, feedback_before, feedback_after
        """
        # MP4+5: Receive & collect feedback BEFORE action
        feedback_before = self.adapter.get_feedbacks()

        # MP1: Send action to environment
        self.adapter.send_action_dict(action)

        # MP2: Perform action (environment executes for one frame)
        self.adapter.wait_one_tick()

        # MP4+5: Receive & collect feedback AFTER action
        feedback_after = self.adapter.get_feedbacks()

        # MP3+6: Record action + record feedback
        result = {
            'frame_id': self.frame_id,
            'action': action,
            'feedback_before': feedback_before,
            'feedback_after': feedback_after,
        }
        self.history.append(result)

        # Record to knowledge graph (if initialized)
        if self.knowledge and self._graph_available:
            try:
                self.knowledge.record_transition_simple(
                    from_frame_id=self.frame_id,
                    from_feedbacks=feedback_before,
                    action=action,
                    to_frame_id=self.frame_id + 1,
                    to_feedbacks=feedback_after
                )
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR] Graph recording failed for frame {self.frame_id}: {e}")

        self.frame_id += 1
        return result

    def get_feedbacks(self) -> Dict:
        """MP4+5: Just receive+collect (no action)."""
        return self.adapter.get_feedbacks()

    def query_frame(self, frame_id: int) -> Optional[Dict]:
        """
        BRAIN-07: Query a recorded frame (from history or graph).

        First checks in-memory history, then falls back to graph query
        if knowledge manager is connected.

        Args:
            frame_id: Frame number to query

        Returns:
            Frame data dict or None if not found
        """
        # First check in-memory history
        for entry in self.history:
            if entry['frame_id'] == frame_id:
                return entry
        # Fall back to graph query if connected
        if self.knowledge and self.knowledge._connected:
            return self.knowledge.get_frame(frame_id)
        return None

    def get_history(self, n: int = None) -> List[Dict]:
        """
        Return last n frames from in-memory history.

        Args:
            n: Number of recent frames to return (None = all)

        Returns:
            List of frame result dicts
        """
        if n is None:
            return list(self.history)
        return list(self.history[-n:])

    def reset(self):
        """Reset frame counter and history."""
        self.frame_id = 0
        self.history = []

    def initialize_graph(self, host: str = 'localhost', port: int = 6379) -> bool:
        """
        BRAIN-08: Initialize knowledge graph connection.

        Attempts to connect the knowledge manager to FalkorDB.
        Sets self._graph_available flag. If connection fails,
        orchestrator still works via in-memory history only.

        Args:
            host: FalkorDB host
            port: FalkorDB port

        Returns:
            True if graph connection succeeded
        """
        self._graph_available = False
        if not self.knowledge:
            return False
        if self.knowledge.connect(host=host, port=port):
            self._graph_available = True
            return True
        return False

    def compare_to_known(self, current_feedbacks: Dict) -> Optional[Dict]:
        """
        BRAIN-09: Compare current state vs known state.

        Sutton: 'awareness is just comparing where I think I am
        and what the environment tells that I am' -- Jan 9

        If we have prior frames, compare current feedbacks to the
        last recorded frame's feedback_after. Returns dict with
        per-variable deltas, or None if no prior frames.

        Args:
            current_feedbacks: Current feedback values from environment

        Returns:
            Dict with expected, actual, deltas, frame_id -- or None if no history
        """
        if not self.history:
            return None
        last = self.history[-1]
        last_feedbacks = last['feedback_after']
        deltas = {}
        for key in current_feedbacks:
            if key in last_feedbacks:
                try:
                    deltas[key] = current_feedbacks[key] - last_feedbacks[key]
                except (TypeError, ValueError):
                    pass  # Skip non-numeric fields
        return {
            'expected': last_feedbacks,
            'actual': current_feedbacks,
            'deltas': deltas,
            'frame_id': last['frame_id'],
        }
