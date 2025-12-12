"""
MEMORY HANDLER
Manages short-term and long-term memory

MEMORY CONCEPTS:
- Long-term Memory: FalkorDB knowledge graphs (permanent knowledge)
- Short-term Memory: Dictionaries, recent episodes (temporary)

SHORT-TERM MEMORY:
- Last episode actions
- Recent state transitions
- Current exploration actions
- Temporary calculations

LONG-TERM MEMORY:
- All knowledge graphs
- Historical transitions
- Learned patterns
"""

import logging
from typing import Dict, List, Optional, Any
from collections import deque
from dataclasses import dataclass
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EpisodeMemory:
    """Short-term memory of one episode"""
    episode_number: int
    start_frame: int
    end_frame: int
    states: List[Any]
    actions: List[Dict[str, any]]
    rewards: List[float]
    timestamp: float


class MemoryHandler:
    """
    Manages short-term and long-term memory
    
    SHORT-TERM (Dictionaries/Fast):
    - Last N episodes
    - Recent actions from current state
    - Temporary exploration data
    
    LONG-TERM (FalkorDB/Persistent):
    - All knowledge graphs
    - Complete transition history
    - Learned patterns
    """
    
    def __init__(self, 
                 short_term_capacity: int = 10,
                 action_memory_size: int = 1000):
        """
        Initialize memory handler
        
        Args:
            short_term_capacity: Number of recent episodes to keep
            action_memory_size: Size of action memory buffer
        """
        # Short-term memory (fast access)
        self.recent_episodes: deque = deque(maxlen=short_term_capacity)
        self.last_episode: Optional[EpisodeMemory] = None
        
        # Action memory (recent actions from each state)
        self.recent_actions: Dict[str, deque] = {}  # state_key -> actions
        self.action_memory_size = action_memory_size
        
        # Current episode buffer
        self.current_episode_buffer = {
            'states': [],
            'actions': [],
            'rewards': [],
            'start_frame': None
        }
        
        # Statistics
        self.episodes_recorded = 0
        self.short_term_queries = 0
        self.long_term_queries = 0
        
        logger.info("[MEMORY] Memory Handler initialized")
    
    def start_episode(self, episode_number: int, start_frame: int):
        """Start recording new episode"""
        self.current_episode_buffer = {
            'episode_number': episode_number,
            'states': [],
            'actions': [],
            'rewards': [],
            'start_frame': start_frame
        }
        logger.info(f"[MEMORY] Started episode {episode_number} @ frame {start_frame}")
    
    def record_transition(self,
                         state: Any,
                         action: Dict[str, any],
                         reward: float = 0.0):
        """
        Record transition to current episode buffer
        
        Args:
            state: State information
            action: Action taken
            reward: Reward received
        """
        self.current_episode_buffer['states'].append(state)
        self.current_episode_buffer['actions'].append(action)
        self.current_episode_buffer['rewards'].append(reward)
    
    def end_episode(self, end_frame: int) -> EpisodeMemory:
        """
        End current episode and move to short-term memory
        
        Args:
            end_frame: Frame where episode ended
        
        Returns:
            Episode memory object
        """
        episode = EpisodeMemory(
            episode_number=self.current_episode_buffer.get('episode_number', 0),
            start_frame=self.current_episode_buffer['start_frame'],
            end_frame=end_frame,
            states=self.current_episode_buffer['states'].copy(),
            actions=self.current_episode_buffer['actions'].copy(),
            rewards=self.current_episode_buffer['rewards'].copy(),
            timestamp=time.time()
        )
        
        # Add to short-term memory
        self.recent_episodes.append(episode)
        self.last_episode = episode
        self.episodes_recorded += 1
        
        logger.info(
            f"[MEMORY] Episode {episode.episode_number} ended: "
            f"{len(episode.actions)} actions recorded"
        )
        
        # Clear buffer
        self.current_episode_buffer = {
            'states': [],
            'actions': [],
            'rewards': [],
            'start_frame': None
        }
        
        return episode
    
    def get_last_episode(self) -> Optional[EpisodeMemory]:
        """
        Get last episode from short-term memory
        
        Returns:
            Last episode or None
        """
        self.short_term_queries += 1
        return self.last_episode
    
    def get_episode(self, episode_number: int) -> Optional[EpisodeMemory]:
        """
        Get specific episode from short-term memory
        
        Args:
            episode_number: Episode to retrieve
        
        Returns:
            Episode or None if not in short-term memory
        """
        self.short_term_queries += 1
        
        for episode in self.recent_episodes:
            if episode.episode_number == episode_number:
                return episode
        
        return None
    
    def get_action_at_frame(self, frame: int) -> Optional[Dict[str, any]]:
        """
        Get action taken at specific frame from last episode
        
        Args:
            frame: Frame number
        
        Returns:
            Action or None
        """
        if not self.last_episode:
            return None
        
        # Calculate relative position in episode
        if frame < self.last_episode.start_frame or frame > self.last_episode.end_frame:
            return None
        
        relative_pos = frame - self.last_episode.start_frame
        
        if relative_pos < len(self.last_episode.actions):
            return self.last_episode.actions[relative_pos]
        
        return None
    
    def record_state_action(self, state_key: str, action: Dict[str, any]):
        """
        Record action taken from specific state
        
        This is for exploration tracking
        
        Args:
            state_key: String representation of state
            action: Action taken
        """
        if state_key not in self.recent_actions:
            self.recent_actions[state_key] = deque(maxlen=self.action_memory_size)
        
        self.recent_actions[state_key].append(action)
    
    def get_actions_from_state(self, state_key: str) -> List[Dict[str, any]]:
        """
        Get all actions taken from specific state
        
        Args:
            state_key: String representation of state
        
        Returns:
            List of actions
        """
        if state_key not in self.recent_actions:
            return []
        
        return list(self.recent_actions[state_key])
    
    def get_statistics(self) -> Dict[str, any]:
        """Get memory statistics"""
        return {
            'episodes_in_short_term': len(self.recent_episodes),
            'episodes_recorded_total': self.episodes_recorded,
            'last_episode': {
                'number': self.last_episode.episode_number if self.last_episode else None,
                'length': len(self.last_episode.actions) if self.last_episode else 0
            },
            'short_term_queries': self.short_term_queries,
            'long_term_queries': self.long_term_queries,
            'state_action_memory': len(self.recent_actions)
        }
    
    def clear_short_term(self):
        """Clear short-term memory"""
        self.recent_episodes.clear()
        self.last_episode = None
        self.recent_actions.clear()
        logger.info("[MEMORY] Short-term memory cleared")
    
    def reset(self):
        """Reset all memory"""
        self.clear_short_term()
        self.current_episode_buffer = {
            'states': [],
            'actions': [],
            'rewards': [],
            'start_frame': None
        }
        logger.info("[MEMORY] Memory Handler reset")