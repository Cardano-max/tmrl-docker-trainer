"""
TIMESTAMP MANAGER - CORRECTED
Internal system time ONLY, no environment tracking

SUPERVISOR'S PRINCIPLE:
"Internal clock is timestamp manager (system only)"
"External clock is environment (not system's job to manage)"
"Episode timestamp should NOT be there - it's environment!"
"""

import time
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimestampManager:
    """
    Manages INTERNAL system time only
    
    SUPERVISOR'S FRAMEWORK:
    - This is BRAIN CAPACITY (ability to track time)
    - System time = internal clock
    - Environment time = ask when needed (function, not variable)
    
    REMOVED (Environment concerns):
    - Episode tracking
    - Episode timestamps  
    - Frame counting
    - Any external time management
    
    WHAT REMAINS (System concerns):
    - Internal system clock
    - Time tracking for processing
    - Timestamp for intelligence decisions
    """
    
    def __init__(self):
        """
        Initialize internal clock
        
        Supervisor: "Current time is perfect because our system is managing time"
        """
        # Internal system start time
        self.system_start_time = time.time()
        
        # Processing metrics (internal only)
        self.processing_iterations = 0
        
        logger.info("[TIMESTAMP] Internal clock initialized")
    
    def get_current_time(self) -> float:
        """
        Get current internal system time
        
        Supervisor: "This function receives this and gives us this"
        
        Returns:
            float: Seconds since system start (internal time)
        """
        return time.time() - self.system_start_time
    
    def get_time_to_track(self, checkpoint_time: float) -> float:
        """
        Check time relative to checkpoint
        
        Supervisor: "Time to be tracked is when I reach certain point.
                    That time needs to be precise or recognized."
        
        Args:
            checkpoint_time: Target time to check against
        
        Returns:
            float: Time difference from checkpoint
        """
        current = self.get_current_time()
        return abs(current - checkpoint_time)
    
    def record_processing_iteration(self):
        """
        Record one processing cycle
        
        This is internal processing count, NOT environment frames
        """
        self.processing_iterations += 1
    
    def get_processing_rate(self, time_window: float = 1.0) -> float:
        """
        Get processing rate (iterations per second)
        
        Supervisor: "FPS in your mind is internal, not external"
        
        Args:
            time_window: Time window to calculate rate
        
        Returns:
            float: Processing iterations per second
        """
        elapsed = self.get_current_time()
        if elapsed == 0:
            return 0.0
        
        return self.processing_iterations / elapsed
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get internal clock statistics
        
        Returns:
            Dict with internal time metrics only
        """
        return {
            'system_runtime_seconds': self.get_current_time(),
            'processing_iterations': self.processing_iterations,
            'processing_rate_per_sec': self.get_processing_rate()
        }
    
    def reset(self):
        """Reset internal clock"""
        self.system_start_time = time.time()
        self.processing_iterations = 0
        logger.info("[TIMESTAMP] Internal clock reset")


# ============================================================================
# ENVIRONMENT TIME INTERFACE (Separate from System)
# ============================================================================

class EnvironmentTimeInterface:
    """
    Interface for querying environment time
    
    Supervisor: "Environment timestamp = function you call, not variable"
    
    This is NOT part of the system's internal state.
    System asks environment for time when needed.
    """
    
    @staticmethod
    def query_environment_time(environment) -> Dict[str, Any]:
        """
        Query environment for its time information
        
        Supervisor: "Anything environment-related, system doesn't need to know.
                    System can ask."
        
        Args:
            environment: Environment object to query
        
        Returns:
            Dict with environment time info (episodes, frames, etc.)
        """
        # This is a QUERY function, not stored state
        return {
            'episode': getattr(environment, 'current_episode', None),
            'frame': getattr(environment, 'current_frame', None),
            'environment_time': getattr(environment, 'time', None)
        }
    
    @staticmethod
    def is_training_context(environment) -> bool:
        """
        Check if in training context
        
        Supervisor: "Episode means training and environment"
        
        Returns:
            bool: True if environment is training
        """
        return hasattr(environment, 'training') and environment.training