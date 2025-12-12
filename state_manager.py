"""
STATE MANAGER
Manages state representation as vector of node positions across all graphs

STATE CONCEPT:
- State = combination of node positions from ALL knowledge graphs
- Example: [speed_node, lidar0_node, lidar1_node, lidar2_node]
- State is a VECTOR, not individual feedback values

CRITICAL: State is Brain Capacity, not Intelligence
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from exceptions import StateNotFoundError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class StateVector:
    """
    State representation as vector of graph node positions
    
    Attributes:
        graph_positions: Dict mapping graph_name -> node_value
        timestamp: When this state was recorded
        frame: Frame number associated with state
    """
    graph_positions: Dict[str, float]
    timestamp: float
    frame: int
    
    def to_vector(self) -> List[float]:
        """Convert to ordered vector (sorted by graph name)"""
        sorted_keys = sorted(self.graph_positions.keys())
        return [self.graph_positions[k] for k in sorted_keys]
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation"""
        return self.graph_positions.copy()
    
    def __eq__(self, other) -> bool:
        """States are equal if all graph positions match"""
        if not isinstance(other, StateVector):
            return False
        return self.graph_positions == other.graph_positions
    
    def __hash__(self) -> int:
        """Make state hashable for use in sets/dicts"""
        items = tuple(sorted(self.graph_positions.items()))
        return hash(items)
    
    def __repr__(self) -> str:
        """String representation"""
        positions = ", ".join([f"{k}={v:.2f}" for k, v in sorted(self.graph_positions.items())])
        return f"State(frame={self.frame}, [{positions}])"


class StateManager:
    """
    Manages current state, previous state, and state transitions
    
    CONCEPTS:
    - Previous State: Where we came from (memory)
    - Current State: Where we are (awareness)
    - Future State: Where we might go (planning - future)
    
    State Tracking:
    - previous_state: Last known state (in short-term memory)
    - current_state: Current awareness of position
    - state_history: Recent state transitions
    """
    
    def __init__(self, graph_names: List[str]):
        """
        Initialize state manager
        
        Args:
            graph_names: List of knowledge graph names (e.g., ['speed', 'lidar_0', ...])
        """
        self.graph_names = sorted(graph_names)
        
        # State tracking
        self.previous_state: Optional[StateVector] = None
        self.current_state: Optional[StateVector] = None
        
        # State history (short-term memory - last N states)
        self.state_history: List[StateVector] = []
        self.max_history = 1000  # Keep last 1000 states
        
        # Statistics
        self.state_transitions = 0
        self.unique_states_visited = set()
        
        logger.info(f"[STATE] State Manager initialized for {len(graph_names)} graphs")
    
    def update_state(self, 
                     graph_positions: Dict[str, float],
                     frame: int,
                     timestamp: float = None) -> StateVector:
        """
        Update current state (creates new state, moves current to previous)
        
        This is the CRITICAL function for state transitions:
        1. Current state → Previous state (moved to memory)
        2. New state → Current state (awareness)
        
        Args:
            graph_positions: Dict of {graph_name: node_value}
            frame: Current frame number
            timestamp: Timestamp (optional)
        
        Returns:
            New current state
        """
        import time
        
        if timestamp is None:
            timestamp = time.time()
        
        # Create new state
        new_state = StateVector(
            graph_positions=graph_positions,
            timestamp=timestamp,
            frame=frame
        )
        
        # Move current → previous
        if self.current_state is not None:
            self.previous_state = self.current_state
            self.state_transitions += 1
        
        # Update current state (awareness)
        self.current_state = new_state
        
        # Add to history (short-term memory)
        self.state_history.append(new_state)
        if len(self.state_history) > self.max_history:
            self.state_history.pop(0)
        
        # Track unique states
        self.unique_states_visited.add(new_state)
        
        logger.debug(f"[STATE] Updated: {new_state}")
        
        return new_state
    
    def get_current_state(self) -> Optional[StateVector]:
        """
        Get current state (awareness)
        
        Returns:
            Current state or None if not initialized
        """
        return self.current_state
    
    def get_previous_state(self) -> Optional[StateVector]:
        """
        Get previous state (memory)
        
        Returns:
            Previous state or None if not available
        """
        return self.previous_state
    
    def get_state_transition(self) -> Optional[Tuple[StateVector, StateVector]]:
        """
        Get last state transition (previous → current)
        
        Returns:
            (previous_state, current_state) tuple or None
        """
        if self.previous_state and self.current_state:
            return (self.previous_state, self.current_state)
        return None
    
    def what_am_i(self) -> Dict[str, any]:
        """
        CRITICAL FUNCTION: "What Am I?"
        
        Returns complete state awareness across all graphs
        
        Returns:
            Dictionary with:
            - current_position: Node positions in each graph
            - previous_position: Where we came from
            - state_vector: Ordered vector representation
            - frame: Current frame
            - transitions: Number of state changes
        """
        if not self.current_state:
            return {
                'current_position': None,
                'previous_position': None,
                'state_vector': None,
                'frame': None,
                'transitions': self.state_transitions,
                'initialized': False
            }
        
        result = {
            'current_position': self.current_state.graph_positions,
            'previous_position': self.previous_state.graph_positions if self.previous_state else None,
            'state_vector': self.current_state.to_vector(),
            'frame': self.current_state.frame,
            'transitions': self.state_transitions,
            'initialized': True
        }
        
        return result
    
    def get_recent_states(self, n: int = 10) -> List[StateVector]:
        """
        Get N most recent states from history
        
        Args:
            n: Number of recent states
        
        Returns:
            List of recent states (newest first)
        """
        return list(reversed(self.state_history[-n:]))
    
    def find_state_in_history(self, 
                              target_frame: int,
                              tolerance: int = 0) -> Optional[StateVector]:
        """
        Find state at specific frame in history
        
        Args:
            target_frame: Target frame number
            tolerance: Frame tolerance for matching
        
        Returns:
            State at that frame or None
        """
        for state in reversed(self.state_history):
            if abs(state.frame - target_frame) <= tolerance:
                return state
        return None
    
    def get_statistics(self) -> Dict[str, any]:
        """Get state manager statistics"""
        return {
            'graphs': len(self.graph_names),
            'state_transitions': self.state_transitions,
            'unique_states': len(self.unique_states_visited),
            'history_size': len(self.state_history),
            'current_state': str(self.current_state) if self.current_state else None,
            'previous_state': str(self.previous_state) if self.previous_state else None
        }
    
    def reset(self):
        """Reset state manager"""
        self.previous_state = None
        self.current_state = None
        self.state_history.clear()
        self.state_transitions = 0
        # Don't clear unique_states - that's cumulative knowledge
        
        logger.info("[STATE] State Manager reset")