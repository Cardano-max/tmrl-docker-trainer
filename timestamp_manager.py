"""
TIMESTAMP MANAGER V3
Dual timestamp system: Agent internal + Environment external

REQUIREMENT:
"Frame is external (environment counter)"
"Timestamp is internal (system clock)"
"Agent on episode 1000 has high timestamp, but env on frame 2"
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TimestampInfo:
    """
    Complete timestamp information
    
    Attributes:
        agent_timestamp: Internal system clock (accumulated)
        environment_frame: External environment counter
        episode_number: Current episode
        episode_timestamp: Time within episode
        episode_frame: Frame within episode
    """
    agent_timestamp: float      # System internal time (seconds since start)
    environment_frame: int      # Environment frame counter
    episode_number: int         # Current episode number
    episode_timestamp: float    # Time since episode start
    episode_frame: int          # Frame since episode start
    
    def __repr__(self) -> str:
        return (
            f"Timestamp(agent={self.agent_timestamp:.2f}s, "
            f"env_frame={self.environment_frame}, "
            f"ep={self.episode_number}, "
            f"ep_time={self.episode_timestamp:.2f}s, "
            f"ep_frame={self.episode_frame})"
        )


class TimestampManager:
    """
    Manages dual timestamp system
    
    CRITICAL DISTINCTION:
    - Agent timestamp: Accumulates across ALL episodes (system lifetime)
    - Environment timestamp: Frame counter (can reset per episode)
    
    Example:
    - Agent timestamp: 3600.5s (1 hour of operation)
    - Environment frame: 45 (just started new episode)
    """
    
    def __init__(self):
        """Initialize timestamp manager"""
        self.system_start_time = time.time()
        
        # Episode tracking
        self.current_episode = 0
        self.episode_start_time = self.system_start_time
        self.episode_start_frame = 0
        
        # Cumulative tracking
        self.total_frames_processed = 0
        self.total_episodes_completed = 0
        
        # Episode history
        self.episode_durations = []
        self.episode_frame_counts = []
        
        logger.info("[TIMESTAMP] Manager initialized")
    
    def get_current_timestamps(self, environment_frame: int) -> TimestampInfo:
        """
        Get complete timestamp information
        
        Args:
            environment_frame: Current frame from environment
        
        Returns:
            Complete timestamp info with agent and environment times
        """
        current_time = time.time()
        
        # Agent timestamp (system lifetime)
        agent_timestamp = current_time - self.system_start_time
        
        # Episode timestamp
        episode_timestamp = current_time - self.episode_start_time
        
        # Episode frame (relative to episode start)
        episode_frame = environment_frame - self.episode_start_frame
        
        return TimestampInfo(
            agent_timestamp=agent_timestamp,
            environment_frame=environment_frame,
            episode_number=self.current_episode,
            episode_timestamp=episode_timestamp,
            episode_frame=episode_frame
        )
    
    def start_new_episode(self, 
                         episode_number: int,
                         starting_frame: int = 0):
        """
        Start new episode (resets episode-specific timestamps)
        
        Args:
            episode_number: New episode number
            starting_frame: Starting frame for new episode
        """
        # Save previous episode stats
        if self.current_episode > 0:
            episode_duration = time.time() - self.episode_start_time
            self.episode_durations.append(episode_duration)
            self.total_episodes_completed += 1
        
        # Reset episode-specific tracking
        self.current_episode = episode_number
        self.episode_start_time = time.time()
        self.episode_start_frame = starting_frame
        
        logger.info(
            f"[TIMESTAMP] Episode {episode_number} started "
            f"(agent_time={self.get_agent_runtime():.2f}s)"
        )
    
    def record_frame(self, environment_frame: int):
        """Record frame processed"""
        self.total_frames_processed += 1
    
    def get_agent_runtime(self) -> float:
        """Get total agent runtime in seconds"""
        return time.time() - self.system_start_time
    
    def get_episode_runtime(self) -> float:
        """Get current episode runtime in seconds"""
        return time.time() - self.episode_start_time
    
    def get_fps(self) -> float:
        """Calculate frames per second (episode)"""
        episode_runtime = self.get_episode_runtime()
        if episode_runtime == 0:
            return 0.0
        
        episode_frames = self.total_frames_processed
        return episode_frames / episode_runtime
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive timestamp statistics"""
        return {
            'agent': {
                'runtime_seconds': self.get_agent_runtime(),
                'total_episodes': self.total_episodes_completed,
                'total_frames': self.total_frames_processed
            },
            'episode': {
                'number': self.current_episode,
                'runtime_seconds': self.get_episode_runtime(),
                'start_frame': self.episode_start_frame,
                'fps': self.get_fps()
            },
            'history': {
                'avg_episode_duration': (
                    sum(self.episode_durations) / len(self.episode_durations)
                    if self.episode_durations else 0.0
                ),
                'episodes_completed': self.total_episodes_completed
            }
        }
    
    def reset(self):
        """Reset timestamp manager (for testing)"""
        self.__init__()
        logger.info("[TIMESTAMP] Manager reset")