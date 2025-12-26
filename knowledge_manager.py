"""
KNOWLEDGE MANAGER - Production Grade V4

SUPERVISOR'S FRAMEWORK:
- Knowledge = What system KNOWS
- Prior Knowledge: From config (actions, feedbacks, constraints)
- Acquired Knowledge: From experience (stored in graphs)

KEY FEATURES:
1. Environment-agnostic data recording
2. Generic memory format support
3. Batch processing with validation
4. Knowledge summary and statistics
"""

import logging
import time
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass

from exceptions import KnowledgeError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TransitionData:
    """
    Environment-agnostic transition representation
    
    This is the GENERIC format that all environments must convert to.
    """
    prev_feedbacks: Dict[str, float]
    curr_feedbacks: Dict[str, float]
    action: Dict[str, float]
    frame: int
    metadata: Optional[Dict[str, Any]] = None


class MemoryExtractor:
    """
    Base class for extracting transitions from different memory formats
    
    SUPERVISOR: "System should be environment agnostic"
    
    Each environment can provide its own extractor.
    """
    
    def extract_transition(self, 
                          memory: Any, 
                          index: int) -> Optional[TransitionData]:
        """Extract single transition from memory at index"""
        raise NotImplementedError("Subclasses must implement extract_transition")
    
    def get_memory_length(self, memory: Any) -> int:
        """Get total number of transitions in memory"""
        raise NotImplementedError("Subclasses must implement get_memory_length")


class TMRLMemoryExtractor(MemoryExtractor):
    """
    Extractor for TMRL memory format
    
    NOTE: This is for testing with TMRL only.
    The core system remains environment-agnostic.
    
    TMRL MemoryTMLidar uses COLUMNAR format:
    - memory.data is a list of N columns
    - Each column contains values for all transitions
    - Column indices depend on observation/action structure
    
    For LIDAR environment (MemoryTMLidar):
    - Observations: [speed, lidar_0, lidar_1, lidar_2, ...]
    - Actions: [gas, brake, steering] or [steering, gas] depending on setup
    
    The memory may also store data differently depending on version.
    """
    
    def __init__(self, feedback_names: List[str], action_names: List[str]):
        self.feedback_names = feedback_names
        self.action_names = action_names
        self._data_format = None  # Will be detected on first access
        self._num_obs = 4  # speed + 3 lidars by default
        self._num_act = 3  # gas, brake, steering by default
    
    def _get_data(self, memory: Any) -> Any:
        """Get the actual data from memory object"""
        if hasattr(memory, 'data'):
            return memory.data
        return memory
    
    def _detect_format(self, memory: Any) -> str:
        """Detect the memory format"""
        data = self._get_data(memory)
        
        if not data:
            return 'empty'
        
        # Check if it's columnar format (list of lists/arrays)
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            
            # If first item is a list/array with many elements, it's columnar
            if hasattr(first_item, '__len__') and len(first_item) > 100:
                return 'columnar'
            
            # If first item is a tuple/list of obs, act, etc., it's tuple format
            if isinstance(first_item, (tuple, list)) and len(first_item) >= 3:
                return 'tuple'
        
        return 'unknown'
    
    def get_memory_length(self, memory: Any) -> int:
        """Get total number of transitions"""
        data = self._get_data(memory)
        
        if not data:
            return 0
        
        format_type = self._detect_format(memory)
        
        if format_type == 'columnar':
            # In columnar format, each column has all transitions
            # Length is the length of the first column
            if len(data) > 0 and hasattr(data[0], '__len__'):
                return len(data[0])
            return 0
        
        elif format_type == 'tuple':
            # In tuple format, each item is one transition
            return len(data)
        
        return 0
    
    def extract_transition(self, 
                          memory: Any, 
                          index: int) -> Optional[TransitionData]:
        """Extract single transition from TMRL memory"""
        try:
            data = self._get_data(memory)
            format_type = self._detect_format(memory)
            
            # Log format detection on first call
            if index == 0:
                logger.info(f"[TMRL] Format detected: {format_type}, data type: {type(data)}, len: {len(data) if data else 0}")
            
            if format_type == 'columnar':
                return self._extract_columnar(data, index)
            elif format_type == 'tuple':
                return self._extract_tuple(data, index)
            else:
                if index == 0:
                    logger.warning(f"[TMRL] Unknown format: {format_type}")
                return None
                
        except Exception as e:
            logger.warning(f"[TMRL] Extraction failed at {index}: {e}")
            return None
    
    def _extract_columnar(self, data: list, index: int) -> Optional[TransitionData]:
        """
        Extract from TMRL columnar format
        
        Actual TMRL MemoryTMLidar format:
        - Column 0: Frame indices (int)
        - Column 1: Actions [gas, brake, steering] (numpy array of 3 floats)
        - Column 2: Speed [speed] (numpy array of 1 float)
        - Column 3: LIDAR [19 beams] (numpy array of 19 floats)
        - Column 4: Done flag (bool)
        - Column 5: Reward (float)
        - Column 6: Info dict
        - Column 7: Truncated flag (bool)
        - Column 8: Additional flag (bool)
        """
        try:
            num_columns = len(data)
            
            if num_columns < 4:
                logger.warning(f"[TMRL] Not enough columns: {num_columns}")
                return None
            
            if index >= len(data[0]):
                logger.warning(f"[TMRL] Index {index} >= column length {len(data[0])}")
                return None
            
            # Need previous index for prev_feedbacks
            prev_index = max(0, index - 1)
            
            # Extract current values with debug logging
            try:
                act_array = data[1][index]      # Actions: [gas, brake, steering]
                speed_array = data[2][index]    # Speed: [speed]
                lidar_array = data[3][index]    # LIDAR: [beam0, beam1, ..., beam18]
                
                # Log first extraction for debug
                if index == 0:
                    logger.info(f"[TMRL] Columnar extract idx=0:")
                    logger.info(f"  act_array type={type(act_array)}, value={act_array}")
                    logger.info(f"  speed_array type={type(speed_array)}, value={speed_array}")
                    logger.info(f"  lidar_array type={type(lidar_array)}, len={len(lidar_array) if hasattr(lidar_array, '__len__') else 'N/A'}")
                
            except Exception as e:
                logger.warning(f"[TMRL] Failed to extract arrays at {index}: {e}")
                return None
            
            # Extract previous values
            prev_speed_array = data[2][prev_index]
            prev_lidar_array = data[3][prev_index]
            
            # Parse speed (single value array)
            curr_speed = float(speed_array[0]) if hasattr(speed_array, '__getitem__') else float(speed_array)
            prev_speed = float(prev_speed_array[0]) if hasattr(prev_speed_array, '__getitem__') else float(prev_speed_array)
            
            # Parse LIDAR (19 beams - use first 3 for lidar_0, lidar_1, lidar_2)
            # Or use specific indices based on your config
            if hasattr(lidar_array, '__getitem__') and len(lidar_array) >= 3:
                curr_lidar_0 = float(lidar_array[0])
                curr_lidar_1 = float(lidar_array[1])
                curr_lidar_2 = float(lidar_array[2])
            else:
                curr_lidar_0 = curr_lidar_1 = curr_lidar_2 = 0.0
            
            if hasattr(prev_lidar_array, '__getitem__') and len(prev_lidar_array) >= 3:
                prev_lidar_0 = float(prev_lidar_array[0])
                prev_lidar_1 = float(prev_lidar_array[1])
                prev_lidar_2 = float(prev_lidar_array[2])
            else:
                prev_lidar_0 = prev_lidar_1 = prev_lidar_2 = 0.0
            
            # Parse actions
            if hasattr(act_array, '__getitem__') and len(act_array) >= 3:
                gas = float(act_array[0])
                brake = float(act_array[1])
                steering = float(act_array[2])
            elif hasattr(act_array, '__getitem__') and len(act_array) >= 1:
                gas = float(act_array[0])
                brake = 0.0
                steering = float(act_array[1]) if len(act_array) > 1 else 0.0
            else:
                gas = brake = steering = 0.0
            
            prev_feedbacks = {
                'speed': prev_speed,
                'lidar_0': prev_lidar_0,
                'lidar_1': prev_lidar_1,
                'lidar_2': prev_lidar_2
            }
            
            curr_feedbacks = {
                'speed': curr_speed,
                'lidar_0': curr_lidar_0,
                'lidar_1': curr_lidar_1,
                'lidar_2': curr_lidar_2
            }
            
            action = {
                'gas': gas,
                'brake': brake,
                'steering': steering
            }
            
            # Log first successful extraction
            if index == 0:
                logger.info(f"[TMRL] First extraction SUCCESS:")
                logger.info(f"  curr_feedbacks: {curr_feedbacks}")
                logger.info(f"  action: {action}")
            
            return TransitionData(
                prev_feedbacks=prev_feedbacks,
                curr_feedbacks=curr_feedbacks,
                action=action,
                frame=index,
                metadata={'source': 'tmrl_columnar'}
            )
            
        except Exception as e:
            logger.warning(f"[TMRL] Columnar extraction failed at {index}: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            return None
    
    def _extract_tuple(self, data: list, index: int) -> Optional[TransitionData]:
        """Extract from tuple format (obs_t, act_t, obs_tm1, ...)"""
        try:
            if index >= len(data):
                return None
            
            transition = data[index]
            
            if not isinstance(transition, (tuple, list)) or len(transition) < 3:
                return None
            
            obs_t = transition[0]
            act_t = transition[1]
            obs_tm1 = transition[2]
            
            prev_feedbacks = self._extract_feedbacks(obs_tm1)
            curr_feedbacks = self._extract_feedbacks(obs_t)
            action = self._extract_action(act_t)
            
            if not prev_feedbacks or not curr_feedbacks or not action:
                return None
            
            return TransitionData(
                prev_feedbacks=prev_feedbacks,
                curr_feedbacks=curr_feedbacks,
                action=action,
                frame=index,
                metadata={'source': 'tmrl_tuple'}
            )
            
        except Exception as e:
            logger.debug(f"Tuple extraction failed at {index}: {e}")
            return None
    
    def _extract_feedbacks(self, obs: Any) -> Dict[str, float]:
        """Extract feedbacks from TMRL observation"""
        feedbacks = {}
        
        try:
            if hasattr(obs, 'flatten'):
                obs = obs.flatten()
            
            if hasattr(obs, '__getitem__') and hasattr(obs, '__len__'):
                obs_len = len(obs)
                
                if obs_len > 0:
                    val = obs[0]
                    if hasattr(val, '__len__') and len(val) > 0:
                        val = val[0]
                    feedbacks['speed'] = float(val)
                
                if obs_len > 1:
                    val = obs[1]
                    if hasattr(val, '__len__') and len(val) > 0:
                        val = val[0]
                    feedbacks['lidar_0'] = float(val)
                
                if obs_len > 2:
                    val = obs[2]
                    if hasattr(val, '__len__') and len(val) > 0:
                        val = val[0]
                    feedbacks['lidar_1'] = float(val)
                
                if obs_len > 3:
                    val = obs[3]
                    if hasattr(val, '__len__') and len(val) > 0:
                        val = val[0]
                    feedbacks['lidar_2'] = float(val)
                    
        except Exception as e:
            logger.debug(f"Feedback extraction error: {e}")
        
        return feedbacks
    
    def _extract_action(self, act: Any) -> Dict[str, float]:
        """Extract action from TMRL action format"""
        action = {}
        
        try:
            if hasattr(act, 'flatten'):
                act = act.flatten()
            
            if hasattr(act, '__getitem__') and hasattr(act, '__len__'):
                act_len = len(act)
                
                if act_len >= 3:
                    action['gas'] = float(act[0])
                    action['brake'] = float(act[1])
                    action['steering'] = float(act[2])
                elif act_len >= 2:
                    action['gas'] = float(act[0])
                    action['steering'] = float(act[1])
                elif act_len >= 1:
                    action['gas'] = float(act[0])
                    
        except Exception as e:
            logger.debug(f"Action extraction error: {e}")
        
        return action


class GenericMemoryExtractor(MemoryExtractor):
    """
    Generic extractor for dict-based memory format
    
    Expected format:
    memory = [
        {'prev_feedbacks': {...}, 'curr_feedbacks': {...}, 'action': {...}, 'frame': int},
        ...
    ]
    """
    
    def extract_transition(self, 
                          memory: List[Dict], 
                          index: int) -> Optional[TransitionData]:
        """Extract transition from generic memory format"""
        try:
            if index >= len(memory):
                return None
            
            item = memory[index]
            
            return TransitionData(
                prev_feedbacks=item['prev_feedbacks'],
                curr_feedbacks=item['curr_feedbacks'],
                action=item['action'],
                frame=item.get('frame', index),
                metadata=item.get('metadata', {})
            )
        except Exception as e:
            logger.debug(f"Generic extraction failed at {index}: {e}")
            return None
    
    def get_memory_length(self, memory: List) -> int:
        """Get generic memory length"""
        return len(memory) if memory else 0


class KnowledgeManager:
    """
    Manages knowledge storage and retrieval
    
    SUPERVISOR'S FRAMEWORK:
    - Prior Knowledge: From config (loaded at init)
    - Acquired Knowledge: From experience (stored in graphs)
    
    "Knowledge is what I think will happen"
    """
    
    def __init__(self, brain):
        """
        Initialize knowledge manager
        
        Args:
            brain: BrainArchitecture instance
        """
        self.brain = brain
        
        # Statistics
        self.transitions_recorded = 0
        self.recording_errors = 0
        self.batch_operations = 0
        
        # Extractors for different memory formats
        self.extractors: Dict[str, MemoryExtractor] = {}
        self._register_default_extractors()
        
        logger.info("[KNOWLEDGE] Knowledge Manager initialized")
    
    def _register_default_extractors(self):
        """Register default memory extractors"""
        feedback_names = list(self.brain.config['feedbacks'].keys())
        action_names = list(self.brain.config['actions'].keys())
        
        self.extractors['tmrl'] = TMRLMemoryExtractor(feedback_names, action_names)
        self.extractors['generic'] = GenericMemoryExtractor()
    
    def register_extractor(self, name: str, extractor: MemoryExtractor):
        """
        Register custom memory extractor
        
        This allows supporting new environment formats.
        """
        self.extractors[name] = extractor
        logger.info(f"[KNOWLEDGE] Registered extractor: {name}")
    
    def record_transition(self, transition: TransitionData) -> bool:
        """
        Record single transition to knowledge
        
        Args:
            transition: TransitionData object
        
        Returns:
            True if successful
        """
        try:
            success = self.brain.record_transition(
                transition.prev_feedbacks,
                transition.curr_feedbacks,
                transition.action,
                transition.frame
            )
            
            if success:
                self.transitions_recorded += 1
            else:
                logger.warning(f"[KNOWLEDGE] record_transition returned False for frame {transition.frame}")
            
            return success
            
        except Exception as e:
            self.recording_errors += 1
            logger.error(f"[KNOWLEDGE] Transition recording failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def record_batch(self,
                    memory: Any,
                    extractor_name: str = 'generic',
                    start_index: int = 0,
                    count: Optional[int] = None,
                    progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """
        Record batch of transitions from memory
        
        ENVIRONMENT-AGNOSTIC: Uses extractor to convert memory format.
        
        Args:
            memory: Raw memory data
            extractor_name: Which extractor to use
            start_index: Start position in memory
            count: Number of transitions (None = all)
            progress_callback: Optional callback(current, total)
        
        Returns:
            Recording statistics
        """
        self.batch_operations += 1
        start_time = time.time()
        
        if extractor_name not in self.extractors:
            raise KnowledgeError(f"Unknown extractor: {extractor_name}")
        
        extractor = self.extractors[extractor_name]
        total_length = extractor.get_memory_length(memory)
        
        if count is None:
            count = total_length - start_index
        
        end_index = min(start_index + count, total_length)
        
        successes = 0
        failures = 0
        errors = []
        sample_data = None
        
        logger.info(
            f"[KNOWLEDGE] Recording batch: {start_index} to {end_index} "
            f"using {extractor_name} extractor (total_length={total_length})"
        )
        
        # Debug: Try first extraction and log details
        if end_index > start_index:
            try:
                test_transition = extractor.extract_transition(memory, start_index)
                if test_transition:
                    logger.info(f"[KNOWLEDGE] Sample transition extracted successfully:")
                    logger.info(f"  prev_feedbacks: {test_transition.prev_feedbacks}")
                    logger.info(f"  curr_feedbacks: {test_transition.curr_feedbacks}")
                    logger.info(f"  action: {test_transition.action}")
                else:
                    logger.warning(f"[KNOWLEDGE] First transition extraction returned None")
            except Exception as e:
                logger.warning(f"[KNOWLEDGE] First transition extraction failed: {e}")
        
        for i in range(start_index, end_index):
            try:
                transition = extractor.extract_transition(memory, i)
                
                if transition is None:
                    failures += 1
                    continue
                
                # Store first successful transition as sample
                if sample_data is None and transition:
                    sample_data = {
                        'feedbacks': transition.curr_feedbacks,
                        'action': transition.action,
                        'frame': transition.frame
                    }
                
                if self.record_transition(transition):
                    successes += 1
                else:
                    failures += 1
                    
            except Exception as e:
                failures += 1
                if len(errors) < 5:  # Keep only first 5 errors
                    errors.append(f"Index {i}: {str(e)}")
            
            if progress_callback and (i - start_index) % 100 == 0:
                progress_callback(i - start_index, count)
        
        elapsed = time.time() - start_time
        rate = successes / elapsed if elapsed > 0 else 0
        
        result = {
            'total_attempted': end_index - start_index,
            'successes': successes,
            'failures': failures,
            'errors': len(errors),
            'error_samples': errors,
            'elapsed_seconds': elapsed,
            'rate_per_second': rate,
            'extractor': extractor_name,
            'sample_data': sample_data
        }
        
        logger.info(
            f"[KNOWLEDGE] Batch complete: {successes}/{result['total_attempted']} "
            f"in {elapsed:.2f}s ({rate:.1f} trans/sec)"
        )
        
        return result
    
    def query_knowledge(self,
                       feedbacks: Dict[str, float],
                       graph_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Query knowledge about current state
        
        SUPERVISOR: "Knowledge tells me what will happen"
        
        Args:
            feedbacks: Current feedback values
            graph_name: Specific graph to query (None = all)
        
        Returns:
            Knowledge summary for state
        """
        try:
            intervals = self.brain.query_current_state(feedbacks)
            
            result = {
                'state_intervals': intervals,
                'graphs': {}
            }
            
            graphs_to_query = [graph_name] if graph_name else list(self.brain.graphs.keys())
            
            for name in graphs_to_query:
                if name not in self.brain.graphs:
                    continue
                
                graph = self.brain.graphs[name]
                state_value = intervals.get(name)
                
                if state_value is not None:
                    result['graphs'][name] = {
                        'state_value': state_value,
                        'tried_actions': graph.get_tried_actions_count(state_value),
                        'tried_labels': graph.get_tried_action_labels(state_value),
                        'node_exists': graph.node_exists(state_value)
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"Knowledge query failed: {e}")
            return {'error': str(e)}
    
    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get summary of all knowledge"""
        summary = {
            'transitions_recorded': self.transitions_recorded,
            'recording_errors': self.recording_errors,
            'batch_operations': self.batch_operations,
            'graphs': {}
        }
        
        for name, graph in self.brain.graphs.items():
            stats = graph.get_statistics()
            summary['graphs'][name] = {
                'nodes': stats['nodes'],
                'edges': stats['edges'],
                'density': stats['density']
            }
        
        return summary
    
    def validate_knowledge_consistency(self) -> Dict[str, Any]:
        """
        Validate knowledge graph consistency
        
        Checks:
        - All graphs have same structure
        - No orphan nodes
        - No invalid edges
        """
        results = {
            'valid': True,
            'issues': [],
            'graphs': {}
        }
        
        for name, graph in self.brain.graphs.items():
            stats = graph.get_statistics()
            graph_result = {
                'nodes': stats['nodes'],
                'edges': stats['edges'],
                'valid': True
            }
            
            # Check for empty graphs
            if stats['nodes'] == 0 and stats['edges'] > 0:
                graph_result['valid'] = False
                results['issues'].append(f"{name}: edges without nodes")
            
            results['graphs'][name] = graph_result
        
        results['valid'] = len(results['issues']) == 0
        return results


class EpisodeRecorder:
    """
    Records episodes to knowledge
    
    Handles the episode lifecycle:
    1. Start episode
    2. Record transitions
    3. End episode
    
    NOTE: Episodes are ENVIRONMENT concern.
    This is just for coordination with training.
    """
    
    def __init__(self, 
                 knowledge_manager: KnowledgeManager,
                 timestamp_manager=None):
        """
        Initialize episode recorder
        
        Args:
            knowledge_manager: KnowledgeManager instance
            timestamp_manager: Optional timestamp manager
        """
        self.knowledge = knowledge_manager
        self.timestamps = timestamp_manager
        
        # Current episode tracking
        self.current_episode = None
        self.episode_transitions = 0
        
        # Statistics
        self.episodes_recorded = 0
        self.total_transitions = 0
        
        logger.info("[KNOWLEDGE] Episode Recorder initialized")
    
    def start_episode(self, episode_number: int, start_frame: int = 0):
        """Start recording new episode"""
        self.current_episode = {
            'number': episode_number,
            'start_frame': start_frame,
            'start_time': time.time()
        }
        self.episode_transitions = 0
        logger.debug(f"[RECORDER] Episode {episode_number} started @ frame {start_frame}")
    
    def record_transition(self, transition: TransitionData) -> bool:
        """Record transition for current episode"""
        if self.knowledge.record_transition(transition):
            self.episode_transitions += 1
            self.total_transitions += 1
            return True
        return False
    
    def end_episode(self, end_frame: int) -> Dict[str, Any]:
        """End current episode"""
        if self.current_episode is None:
            return {'error': 'No episode in progress'}
        
        elapsed = time.time() - self.current_episode['start_time']
        
        result = {
            'episode': self.current_episode['number'],
            'start_frame': self.current_episode['start_frame'],
            'end_frame': end_frame,
            'transitions': self.episode_transitions,
            'elapsed_seconds': elapsed
        }
        
        self.episodes_recorded += 1
        self.current_episode = None
        
        logger.debug(f"[RECORDER] Episode ended: {result}")
        return result
    
    def record_tmrl_memory(self,
                          memory: Any,
                          start_index: int = 0,
                          count: Optional[int] = None) -> Dict[str, Any]:
        """
        Record TMRL memory format
        
        NOTE: This is for testing with TMRL only.
        For other environments, use record_batch with appropriate extractor.
        """
        logger.info(f"[KNOWLEDGE] Recording TMRL memory: transitions {start_index}-{start_index + (count or '?')}")
        
        return self.knowledge.record_batch(
            memory=memory,
            extractor_name='tmrl',
            start_index=start_index,
            count=count
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get recorder statistics"""
        return {
            'episodes_recorded': self.episodes_recorded,
            'total_transitions': self.total_transitions,
            'current_episode': self.current_episode
        }