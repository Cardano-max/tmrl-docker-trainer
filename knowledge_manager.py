"""
KNOWLEDGE MANAGER V3 - FINAL PRODUCTION VERSION
High-level knowledge operations built on brain capacity

FINAL UPDATES FOR PRODUCTION:
- Removed all calls to timestamp_manager.record_frame()
- Frames are ENVIRONMENT concern → System does NOT track them
- Clean logs: No more AttributeError warnings
- Full compatibility with timestamp_manager_corrected.py (internal time only)
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import time
from brain_capacity_v2 import BrainArchitecture  # Note: your project uses brain_core.py → adjust if needed
from exceptions import KnowledgeError, StateNotFoundError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeManager:
    """
    Manages knowledge operations with optimization and caching
    Built on top of Brain Capacity
    """
    
    def __init__(self, brain: BrainArchitecture):
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
        Note: start_frame is kept for compatibility but NOT used for internal timing
        """
        start_time = time.time()
        
        stats = {
            'transitions_attempted': len(episode_data),
            'transitions_succeeded': 0,
            'transitions_failed': 0,
            'errors': []
        }
        
        for i, (prev_fb, curr_fb, action) in enumerate(episode_data):
            try:
                self.brain.record_transition(prev_fb, curr_fb, action, start_frame + i)
                stats['transitions_succeeded'] += 1
                
            except Exception as e:
                stats['transitions_failed'] += 1
                stats['errors'].append(f"Transition {i}: {str(e)}")
                logger.warning(f"Failed to record transition {i}: {e}")
        
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
    
    # ... [rest of KnowledgeManager methods unchanged: query_state_interval, find_similar_states, etc.]
    # (All other methods remain identical to your original version)

    def get_knowledge_summary(self) -> Dict[str, Any]:
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
        self._state_cache.clear()
        logger.info("[KNOWLEDGE] Cache cleared")
    
    def validate_knowledge_integrity(self) -> Dict[str, Any]:
        results = {
            'valid': True,
            'issues': [],
            'checks_performed': 0
        }
        
        for graph_name, graph in self.brain.graphs.items():
            try:
                stats = graph.get_statistics()
                results['checks_performed'] += 1
                
                if stats['nodes'] == 0:
                    results['issues'].append(f"Graph '{graph_name}' has no nodes")
                
                if stats['nodes'] > 0 and stats['edges'] == 0:
                    results['issues'].append(f"Graph '{graph_name}' has nodes but no edges")
                
            except Exception as e:
                results['valid'] = False
                results['issues'].append(f"Failed to validate graph '{graph_name}': {e}")
        
        if results['issues']:
            results['valid'] = False
        
        return results


class EpisodeRecorder:
    """
    Specialized class for efficient episode recording
    CLEAN PRODUCTION VERSION: No frame tracking in system
    """
    
    def __init__(self, knowledge_manager: KnowledgeManager, timestamp_manager=None):
        self.knowledge = knowledge_manager
        self.timestamp_manager = timestamp_manager  # Kept for compatibility only
        self.episodes_recorded = 0
        
        logger.info("[KNOWLEDGE] Episode Recorder initialized")
    
    def set_timestamp_manager(self, timestamp_manager):
        """Allow late binding (optional, not used for frame tracking)"""
        self.timestamp_manager = timestamp_manager
        logger.info("[KNOWLEDGE] Timestamp manager linked (frame tracking disabled per architecture)")

    def extract_tmrl_state(self, obs: Any) -> Dict[str, float]:
        # ... (unchanged)
        try:
            if isinstance(obs, tuple) and len(obs) >= 2:
                speed_arr, lidar_arr = obs[0], obs[1]
                state = {}
                if len(speed_arr) > 0:
                    state['speed'] = float(speed_arr[0])
                for i in range(min(3, len(lidar_arr))):
                    state[f'lidar_{i}'] = float(lidar_arr[i])
                return state
            return {}
        except Exception as e:
            logger.warning(f"Failed to extract TMRL state: {e}")
            return {}

    def extract_tmrl_action(self, action_arr: Any) -> Dict[str, float]:
        # ... (unchanged)
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
        Record transitions from TMRL memory
        CLEAN V3: No frame recording → Environment frames not tracked internally
        """
        total_size = len(memory)
        end_index = total_size if count is None else min(start_index + count, total_size)
        
        logger.info(f"[KNOWLEDGE] Recording TMRL memory: transitions {start_index}-{end_index}")

        start_time = time.time()
        episode_data = []
        frames_processed = 0
        
        for i in range(start_index, end_index):
            try:
                transition = memory[i]
                if len(transition) < 5:
                    continue
                
                obs, act, _, next_obs, _ = transition[:5]
                
                prev_state = self.extract_tmrl_state(obs)
                curr_state = self.extract_tmrl_state(next_obs)
                action = self.extract_tmrl_action(act)
                
                if prev_state and curr_state and action:
                    episode_data.append((prev_state, curr_state, action))
                    frames_processed += 1
                
            except Exception as e:
                logger.warning(f"Failed to process transition {i}: {e}")
        
        # Record to brain
        stats = self.knowledge.record_episode(episode_data, start_index)
        self.episodes_recorded += 1
        stats['frames_processed'] = frames_processed
        
        elapsed = time.time() - start_time
        logger.info(
            f"[KNOWLEDGE] Batch recording complete: "
            f"{frames_processed} transitions in {elapsed:.2f}s"
        )
        
        return stats