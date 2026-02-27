"""
Offline unit tests for FrameOrchestrator.

Uses MockAdapter (no TMNF/TMInterface needed).
MockAdapter simulates: send_action_dict() stores action,
wait_one_tick() advances internal state, get_feedbacks()
returns state dict with speed that changes based on last action.

12 tests covering all public methods and BRAIN-07/08/09 capacities.
"""

import pytest
from core.frame_orchestrator import FrameOrchestrator


class MockAdapter:
    """
    Mock adapter simulating TMNF frame-sync behavior.

    - send_action_dict(): stores the action
    - wait_one_tick(): applies action to internal state (speed changes)
    - get_feedbacks(): returns current state dict
    """

    def __init__(self):
        self.speed = 0.0
        self.last_action = {}
        self.actions_received = []
        self.tick_count = 0

    def send_action_dict(self, action: dict):
        """Store the action to apply on next tick."""
        self.last_action = action.copy()
        self.actions_received.append(action.copy())

    def wait_one_tick(self):
        """Apply last action to internal state."""
        self.tick_count += 1
        # Gas increases speed by 5.0 per tick
        if self.last_action.get('gas', 0) > 0:
            self.speed += 5.0
        # Brake decreases speed by 3.0 per tick (floor at 0)
        if self.last_action.get('brake', 0) > 0:
            self.speed = max(0.0, self.speed - 3.0)

    def get_feedbacks(self):
        """Return current state."""
        return {'speed': self.speed}


class MockKnowledgeManager:
    """Minimal mock for testing graph-related behavior."""

    def __init__(self):
        self._connected = False
        self.transitions = []

    def connect(self, host='localhost', port=6379):
        """Simulate connection -- always fails (no FalkorDB in tests)."""
        return False

    def record_transition_simple(self, from_frame_id, from_feedbacks,
                                  action, to_frame_id, to_feedbacks):
        """Record transition in memory."""
        self.transitions.append({
            'from_frame_id': from_frame_id,
            'from_feedbacks': from_feedbacks,
            'action': action,
            'to_frame_id': to_frame_id,
            'to_feedbacks': to_feedbacks,
        })
        return True

    def get_frame(self, frame_id):
        """Simulate graph query."""
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFrameOrchestrator:
    """12 offline tests for FrameOrchestrator."""

    def test_execute_one_frame_records_history(self):
        """Execute 5 frames, verify history has 5 entries."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        for _ in range(5):
            orch.execute_one_frame({'gas': 1.0, 'brake': 0.0})

        assert len(orch.history) == 5

    def test_frame_id_increments(self):
        """Verify sequential frame IDs."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        results = []
        for _ in range(3):
            results.append(orch.execute_one_frame({'gas': 1.0}))

        assert results[0]['frame_id'] == 0
        assert results[1]['frame_id'] == 1
        assert results[2]['frame_id'] == 2
        assert orch.frame_id == 3

    def test_feedback_before_after_captured(self):
        """Before != after when action has effect (gas increases speed)."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        result = orch.execute_one_frame({'gas': 1.0})

        # Before: speed=0.0 (initial), After: speed=5.0 (gas applied)
        assert result['feedback_before']['speed'] == 0.0
        assert result['feedback_after']['speed'] == 5.0

    def test_no_knowledge_manager_still_works(self):
        """Orchestrator works without FalkorDB (knowledge_manager=None)."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter, knowledge_manager=None)

        result = orch.execute_one_frame({'gas': 1.0})

        assert result['frame_id'] == 0
        assert result['feedback_after']['speed'] == 5.0
        assert len(orch.history) == 1

    def test_reset_clears_state(self):
        """frame_id resets to 0, history clears."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        for _ in range(5):
            orch.execute_one_frame({'gas': 1.0})

        assert orch.frame_id == 5
        assert len(orch.history) == 5

        orch.reset()

        assert orch.frame_id == 0
        assert len(orch.history) == 0

    def test_get_history_returns_last_n(self):
        """Partial history retrieval."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        for _ in range(10):
            orch.execute_one_frame({'gas': 1.0})

        last_3 = orch.get_history(3)
        assert len(last_3) == 3
        assert last_3[0]['frame_id'] == 7
        assert last_3[1]['frame_id'] == 8
        assert last_3[2]['frame_id'] == 9

        all_history = orch.get_history()
        assert len(all_history) == 10

    def test_action_dict_forwarded_to_adapter(self):
        """Verify adapter receives correct action."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        action = {'gas': 1.0, 'brake': 0.0, 'left': 1.0, 'right': 0.0}
        orch.execute_one_frame(action)

        assert len(adapter.actions_received) == 1
        assert adapter.actions_received[0] == action

    def test_query_frame_returns_from_history(self):
        """BRAIN-07: query_frame(2) returns frame 2 data from history."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        for _ in range(5):
            orch.execute_one_frame({'gas': 1.0})

        frame_2 = orch.query_frame(2)
        assert frame_2 is not None
        assert frame_2['frame_id'] == 2

    def test_query_frame_returns_none_for_missing(self):
        """query_frame(999) returns None."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        orch.execute_one_frame({'gas': 1.0})

        assert orch.query_frame(999) is None

    def test_compare_to_known_returns_deltas(self):
        """BRAIN-09: after 3 frames, compare_to_known returns expected/actual/deltas."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        # Execute 3 frames with gas (speed: 0->5->10->15)
        for _ in range(3):
            orch.execute_one_frame({'gas': 1.0})

        # Last feedback_after was speed=15.0
        # Compare with a new reading of speed=17.0
        comparison = orch.compare_to_known({'speed': 17.0})

        assert comparison is not None
        assert comparison['expected']['speed'] == 15.0
        assert comparison['actual']['speed'] == 17.0
        assert comparison['deltas']['speed'] == 2.0
        assert comparison['frame_id'] == 2  # Last frame was frame_id=2

    def test_compare_to_known_returns_none_when_empty(self):
        """compare_to_known before any frames returns None."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter)

        assert orch.compare_to_known({'speed': 5.0}) is None

    def test_initialize_graph_without_knowledge_manager(self):
        """BRAIN-08: initialize_graph returns False if no knowledge_manager."""
        adapter = MockAdapter()
        orch = FrameOrchestrator(adapter, knowledge_manager=None)

        result = orch.initialize_graph()

        assert result is False
        assert orch._graph_available is False
