"""
KNOWLEDGE MANAGER V3
High-level knowledge operations built on brain capacity

UPDATES FOR V3:
- Integration with timestamp manager
- Proper frame tracking during batch recording
- Enhanced performance monitoring
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import time

from brain_capacity_v2 import BrainArchitecture
from exceptions import KnowledgeError, StateNotFoundError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeManager:
    """
    Manages knowledge operations with optimization and caching
    
    Built on top of Brain Capacity
    """
    
    def __init__(self, brain: BrainArchitecture):
        """
        Initialize knowledge manager
        
        Args:
            brain: Initialized brain architecture
        """
        self.brain = brain
        
        # Caching for performance
        self._state_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Performance tracking
        self._operation_times = defaultdict(list)
        
        logger.info("[KNOWLEDGE] Knowledge Manager initialized")
    
    def record_episode(self,
                      episode_data: List[Tuple[Dict, Dict, Dict]],
                      start_frame: int) -> Dict[str, Any]:
        """
        Record entire episode efficiently
        
        Args:
            episode_data: List of (prev_feedbacks, curr_feedbacks, action) tuples
            start_frame: Starting frame number
        
        Returns:
            Recording statistics
        """
        start_time = time.time()
        
        stats = {
            'transitions_attempted': len(episode_data),
            'transitions_succeeded': 0,
            'transitions_failed': 0,
            'errors': []
        }
        
        for i, (prev_fb, curr_fb, action) in enumerate(episode_data):
            frame = start_frame + i
            
            try:
                self.brain.record_transition(prev_fb, curr_fb, action, frame)
                stats['transitions_succeeded'] += 1
                
            except Exception as e:
                stats['transitions_failed'] += 1
                stats['errors'].append(f"Frame {frame}: {str(e)}")
                logger.warning(f"Failed to record frame {frame}: {e}")
        
        elapsed = time.time() - start_time
        stats['time_elapsed'] = elapsed
        stats['transitions_per_second'] = stats['transitions_succeeded'] / elapsed if elapsed > 0 else 0
        
        self._operation_times['record_episode'].append(elapsed)
        
        logger.info(
            f"[KNOWLEDGE] Episode recorded: "
            f"{stats['transitions_succeeded']}/{stats['transitions_attempted']} transitions "
            f"in {elapsed:.2f}s ({stats['transitions_per_second']:.1f} trans/sec)"
        )
        
        return stats
    
    def query_state_interval(self, feedbacks: Dict[str, float]) -> Dict[str, float]:
        """
        Query state intervals with caching
        
        Args:
            feedbacks: Raw feedback values
        
        Returns:
            Interval values (cached if possible)
        """
        # Create cache key
        cache_key = tuple(sorted(feedbacks.items()))
        
        if cache_key in self._state_cache:
            self._cache_hits += 1
            return self._state_cache[cache_key]
        
        self._cache_misses += 1
        
        # Query brain
        intervals = self.brain.query_current_state(feedbacks)
        
        # Cache result
        self._state_cache[cache_key] = intervals
        
        # Limit cache size
        if len(self._state_cache) > 10000:
            # Remove oldest 1000 entries
            keys_to_remove = list(self._state_cache.keys())[:1000]
            for key in keys_to_remove:
                del self._state_cache[key]
        
        return intervals
    
    def find_similar_states(self,
                           target_feedbacks: Dict[str, float],
                           tolerance: float = 1.0) -> List[Dict[str, float]]:
        """
        Find states similar to target within tolerance
        
        Args:
            target_feedbacks: Target state
            tolerance: Tolerance multiplier for interval size
        
        Returns:
            List of similar state intervals
        """
        # Get target interval
        target_interval = self.query_state_interval(target_feedbacks)
        
        similar_states = []
        
        # For each feedback, find nearby intervals
        for feedback_name, target_value in target_interval.items():
            feedback_config = self.brain.config['feedbacks'][feedback_name]
            interval_size = feedback_config['interval_size']
            
            # Calculate range
            min_val = target_value - (interval_size * tolerance)
            max_val = target_value + (interval_size * tolerance)
            
            # Generate intervals in range
            current = min_val
            while current <= max_val:
                similar_states.append({feedback_name: current})
                current += interval_size
        
        return similar_states
    
    def get_exploration_status(self, feedbacks: Dict[str, float]) -> Dict[str, Any]:
        """
        Get exploration status for current state
        
        Args:
            feedbacks: Current state feedbacks
        
        Returns:
            Exploration status dictionary
        """
        intervals = self.query_state_interval(feedbacks)
        
        tried_count = self.brain.get_tried_actions_count(feedbacks)
        max_count = self.brain.get_max_action_combinations()
        
        status = {
            'state_intervals': intervals,
            'actions_tried': tried_count,
            'actions_remaining': max_count - tried_count,
            'exploration_percentage': (tried_count / max_count * 100) if max_count > 0 else 0,
            'fully_explored': tried_count >= max_count
        }
        
        return status
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive knowledge summary
        
        Returns:
            Knowledge statistics and analysis
        """
        system_stats = self.brain.get_system_statistics()
        
        summary = {
            'system_info': system_stats['system'],
            'knowledge_graphs': system_stats['graphs'],
            'cache_performance': {
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses) 
                           if (self._cache_hits + self._cache_misses) > 0 else 0,
                'cache_size': len(self._state_cache)
            },
            'performance': {}
        }
        
        # Calculate average operation times
        for op_name, times in self._operation_times.items():
            if times:
                summary['performance'][op_name] = {
                    'count': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times)
                }
        
        return summary
    
    def clear_cache(self):
        """Clear internal caches"""
        self._state_cache.clear()
        logger.info("[KNOWLEDGE] Cache cleared")
    
    def validate_knowledge_integrity(self) -> Dict[str, Any]:
        """
        Validate knowledge graph integrity
        
        Returns:
            Validation results
        """
        results = {
            'valid': True,
            'issues': [],
            'checks_performed': 0
        }
        
        for graph_name, graph in self.brain.graphs.items():
            try:
                stats = graph.get_statistics()
                results['checks_performed'] += 1
                
                # Check if graph has data
                if stats['nodes'] == 0:
                    results['issues'].append(
                        f"Graph '{graph_name}' has no nodes"
                    )
                
                # Check for orphaned nodes
                if stats['nodes'] > 0 and stats['edges'] == 0:
                    results['issues'].append(
                        f"Graph '{graph_name}' has nodes but no edges"
                    )
                
            except Exception as e:
                results['valid'] = False
                results['issues'].append(
                    f"Failed to validate graph '{graph_name}': {e}"
                )
        
        if results['issues']:
            results['valid'] = False
        
        return results


class EpisodeRecorder:
    """
    Specialized class for efficient episode recording
    Handles TMRL checkpoint processing with V3 timestamp tracking
    """
    
    def __init__(self, knowledge_manager: KnowledgeManager, timestamp_manager=None):
        """
        Initialize episode recorder
        
        Args:
            knowledge_manager: Knowledge manager instance
            timestamp_manager: Optional timestamp manager for frame tracking
        """
        self.knowledge = knowledge_manager
        self.timestamp_manager = timestamp_manager
        self.episodes_recorded = 0
        
        logger.info("[KNOWLEDGE] Episode Recorder initialized")
    
    def set_timestamp_manager(self, timestamp_manager):
        """
        Set timestamp manager (for late binding)
        
        Args:
            timestamp_manager: Timestamp manager instance
        """
        self.timestamp_manager = timestamp_manager
        logger.info("[KNOWLEDGE] Timestamp manager linked to Episode Recorder")
    
    def extract_tmrl_state(self, obs: Any) -> Dict[str, float]:
        """
        Extract state from TMRL observation
        
        Args:
            obs: TMRL observation tuple (speed_array, lidar_array)
        
        Returns:
            State dictionary
        """
        try:
            if isinstance(obs, tuple) and len(obs) >= 2:
                speed_arr, lidar_arr = obs[0], obs[1]
                
                state = {}
                
                # Speed
                if len(speed_arr) > 0:
                    state['speed'] = float(speed_arr[0])
                
                # LIDAR beams (first 3)
                for i in range(min(3, len(lidar_arr))):
                    state[f'lidar_{i}'] = float(lidar_arr[i])
                
                return state
            
            return {}
            
        except Exception as e:
            logger.warning(f"Failed to extract TMRL state: {e}")
            return {}
    
    def extract_tmrl_action(self, action_arr: Any) -> Dict[str, float]:
        """
        Extract action from TMRL action array
        
        Args:
            action_arr: TMRL action array [gas, brake, steering]
        
        Returns:
            Action dictionary
        """
        try:
            if hasattr(action_arr, '__len__') and len(action_arr) >= 3:
                return {
                    'gas': float(action_arr[0]),
                    'brake': float(action_arr[1]),
                    'steering': float(action_arr[2])
                }
            return {}
            
        except Exception as e:
            logger.warning(f"Failed to extract TMRL action: {e}")
            return {}
    
    def record_tmrl_memory(self,
                          memory: Any,
                          start_index: int = 0,
                          count: Optional[int] = None) -> Dict[str, Any]:
        """
        Record transitions from TMRL memory with V3 timestamp tracking
        
        CRITICAL V3 UPDATE:
        - Records each frame to timestamp manager
        - Tracks agent timestamp and environment frame
        
        Args:
            memory: TMRL MemoryTMLidar object
            start_index: Starting index in memory
            count: Number of transitions to process (None = all)
        
        Returns:
            Recording statistics
        """
        total_size = len(memory)
        
        if count is None:
            end_index = total_size
        else:
            end_index = min(start_index + count, total_size)
        
        logger.info(
            f"[KNOWLEDGE] Recording TMRL memory: "
            f"transitions {start_index}-{end_index} (total: {total_size})"
        )
        
        start_time = time.time()
        episode_data = []
        frames_processed = 0
        
        for i in range(start_index, end_index):
            try:
                transition = memory[i]
                
                if len(transition) < 5:
                    continue
                
                obs, act, rew, next_obs, done = transition[:5]
                
                # Extract states
                prev_state = self.extract_tmrl_state(obs)
                curr_state = self.extract_tmrl_state(next_obs)
                action = self.extract_tmrl_action(act)
                
                if prev_state and curr_state and action:
                    episode_data.append((prev_state, curr_state, action))
                    
                    # V3 CRITICAL: Track frame in timestamp manager
                    if self.timestamp_manager:
                        self.timestamp_manager.record_frame(i)
                    
                    frames_processed += 1
                
            except Exception as e:
                logger.warning(f"Failed to process transition {i}: {e}")
        
        # Record episode
        stats = self.knowledge.record_episode(episode_data, start_index)
        self.episodes_recorded += 1
        
        # Add timestamp tracking info to stats
        stats['frames_processed'] = frames_processed
        
        elapsed = time.time() - start_time
        logger.info(
            f"[KNOWLEDGE] Batch complete: "
            f"{frames_processed} frames tracked in timestamp manager"
        )
        
        return stats