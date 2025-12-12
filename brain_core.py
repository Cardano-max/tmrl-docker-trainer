"""
BRAIN CAPACITY V2 - With State Management & Generic Queries

CRITICAL UPDATES:
1. Generic query functions (not hardcoded gas/brake/steering)
2. Integration with StateManager for "What Am I?" 
3. State-aware operations
4. Returns action combinations from config, not specific actions
"""

import json
import logging
import math
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from itertools import product
from functools import lru_cache
from falkordb import FalkorDB

from exceptions import *
from validators import ConfigValidator, InputValidator
from state_manager import StateManager, StateVector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ActionDiscretizer:
    """Discretizes continuous actions to bins with caching"""
    
    def __init__(self, actions_config: Dict[str, Any]):
        """Initialize from validated configuration"""
        try:
            self.config = actions_config
            self.action_names = sorted(list(actions_config.keys()))
            
            # Pre-compute all combinations
            self.all_combinations = self._generate_all_combinations()
            
            # Create lookup maps for fast discretization
            self._bin_lookup = self._create_bin_lookup()
            
            logger.info(
                f"[BRAIN] Action Discretizer initialized: "
                f"{len(self.action_names)} actions, "
                f"{len(self.all_combinations)} combinations"
            )
            
        except Exception as e:
            raise DiscretizationError(f"Failed to initialize ActionDiscretizer: {e}")
    
    def _create_bin_lookup(self) -> Dict[str, List[Tuple[float, float, str]]]:
        """Create efficient lookup structure for bins"""
        lookup = {}
        for action_name, action_config in self.config.items():
            bins = [(b['min'], b['max'], b['label']) 
                   for b in action_config['bins']]
            lookup[action_name] = sorted(bins, key=lambda x: x[0])
        return lookup
    
    def _generate_all_combinations(self) -> List[Dict[str, str]]:
        """Generate all possible action combinations"""
        try:
            action_labels = {}
            for action_name in self.action_names:
                labels = [bin_info['label'] 
                         for bin_info in self.config[action_name]['bins']]
                action_labels[action_name] = labels
            
            combinations = []
            label_lists = [action_labels[name] for name in self.action_names]
            
            for combo_tuple in product(*label_lists):
                combo_dict = {
                    name: label 
                    for name, label in zip(self.action_names, combo_tuple)
                }
                combinations.append(combo_dict)
            
            return combinations
            
        except Exception as e:
            raise DiscretizationError(f"Failed to generate combinations: {e}")
    
    @lru_cache(maxsize=10000)
    def _discretize_single_cached(self, action_name: str, value: float) -> str:
        """Cached discretization for single action"""
        bins = self._bin_lookup[action_name]
        
        for min_val, max_val, label in bins:
            if min_val <= value < max_val:
                return label
        
        return bins[-1][2]
    
    def discretize(self, continuous_actions: Dict[str, float]) -> Dict[str, str]:
        """Discretize continuous actions to labels"""
        try:
            InputValidator.validate_action(continuous_actions, self.action_names)
            
            discrete = {}
            for action_name in self.action_names:
                value = continuous_actions[action_name]
                discrete[action_name] = self._discretize_single_cached(
                    action_name, value
                )
            
            return discrete
            
        except ValidationError as e:
            raise DiscretizationError(f"Validation failed: {e}")
        except Exception as e:
            raise DiscretizationError(f"Discretization failed: {e}")
    
    def get_max_combinations(self) -> int:
        """Get total number of possible action combinations"""
        return len(self.all_combinations)
    
    def get_combination_index(self, discrete_actions: Dict[str, str]) -> int:
        """Get index of action combination"""
        try:
            return self.all_combinations.index(discrete_actions)
        except ValueError:
            return -1
    
    def get_action_names(self) -> List[str]:
        """Get list of action names (generic)"""
        return self.action_names.copy()


class FeedbackDiscretizer:
    """Discretizes continuous feedback to intervals with caching"""
    
    def __init__(self, feedbacks_config: Dict[str, Any]):
        """Initialize from validated configuration"""
        try:
            self.config = feedbacks_config
            self.feedback_names = sorted(list(feedbacks_config.keys()))
            
            self._interval_params = {}
            for name, config in feedbacks_config.items():
                self._interval_params[name] = {
                    'size': config['interval_size'],
                    'min': config['expected_range'][0],
                    'max': config['expected_range'][1]
                }
            
            logger.info(
                f"[BRAIN] Feedback Discretizer initialized: "
                f"{len(self.feedback_names)} feedbacks"
            )
            
        except Exception as e:
            raise DiscretizationError(f"Failed to initialize FeedbackDiscretizer: {e}")
    
    @lru_cache(maxsize=50000)
    def _discretize_single_cached(self, feedback_name: str, value: float) -> float:
        """Cached discretization for single feedback"""
        params = self._interval_params[feedback_name]
        interval_size = params['size']
        
        bin_index = math.floor(value / interval_size)
        interval_center = bin_index * interval_size + (interval_size / 2.0)
        
        return round(interval_center, 6)
    
    def discretize(self, feedback_name: str, value: float) -> float:
        """Discretize single feedback value to interval"""
        try:
            if feedback_name not in self.config:
                raise DiscretizationError(f"Unknown feedback: {feedback_name}")
            
            params = self._interval_params[feedback_name]
            if not (params['min'] <= value <= params['max']):
                logger.warning(
                    f"Feedback '{feedback_name}' value {value} "
                    f"outside expected range [{params['min']}, {params['max']}]"
                )
            
            return self._discretize_single_cached(feedback_name, value)
            
        except Exception as e:
            raise DiscretizationError(
                f"Failed to discretize '{feedback_name}': {e}"
            )
    
    def discretize_all(self, feedbacks: Dict[str, float]) -> Dict[str, float]:
        """Discretize all feedbacks to intervals"""
        try:
            InputValidator.validate_feedbacks(feedbacks, self.feedback_names)
            
            discrete = {}
            for name, value in feedbacks.items():
                if name in self.config:
                    discrete[name] = self.discretize(name, value)
            
            return discrete
            
        except ValidationError as e:
            raise DiscretizationError(f"Validation failed: {e}")
        except Exception as e:
            raise DiscretizationError(f"Discretization failed: {e}")


class KnowledgeGraph:
    """Single knowledge graph for one feedback type"""
    
    def __init__(self, 
                 feedback_name: str,
                 db: FalkorDB,
                 retry_attempts: int = 3,
                 retry_delay: float = 1.0):
        """Initialize knowledge graph"""
        try:
            self.feedback_name = feedback_name
            self.graph_name = f"kb_{feedback_name}"
            self.retry_attempts = retry_attempts
            self.retry_delay = retry_delay
            
            self.graph = db.select_graph(self.graph_name)
            self._create_indices()
            
            self.stats = {
                'nodes_created': 0,
                'edges_created': 0,
                'queries_executed': 0,
                'errors': 0
            }
            
            logger.info(f"[BRAIN] Knowledge graph '{feedback_name}' initialized")
            
        except Exception as e:
            raise GraphOperationError(
                f"Failed to initialize graph '{feedback_name}': {e}"
            )
    
    def _create_indices(self):
        """Create database indices for performance"""
        try:
            self.graph.query("CREATE INDEX FOR (n:State) ON (n.value)")
            logger.debug(f"[{self.feedback_name}] Created indices")
        except Exception as e:
            logger.debug(f"[{self.feedback_name}] Index creation: {e}")
    
    def _execute_with_retry(self, operation: callable, *args, **kwargs) -> Any:
        """Execute database operation with retry logic"""
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                result = operation(*args, **kwargs)
                self.stats['queries_executed'] += 1
                return result
                
            except Exception as e:
                last_exception = e
                self.stats['errors'] += 1
                
                if attempt < self.retry_attempts - 1:
                    logger.warning(
                        f"[{self.feedback_name}] Retry {attempt + 1}/{self.retry_attempts}: {e}"
                    )
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"[{self.feedback_name}] All retries failed: {e}"
                    )
        
        raise GraphOperationError(
            f"Operation failed after {self.retry_attempts} attempts: {last_exception}"
        )
    
    def node_exists(self, interval_value: float) -> bool:
        """Check if node exists for this interval value"""
        def _check():
            result = self.graph.query(
                f"MATCH (n:State {{value: {interval_value}}}) RETURN n LIMIT 1"
            )
            return len(result.result_set) > 0
        
        try:
            return self._execute_with_retry(_check)
        except GraphOperationError:
            return False
    
    def create_node(self, interval_value: float, frame: int) -> bool:
        """Create new state node"""
        if self.node_exists(interval_value):
            return False
        
        def _create():
            self.graph.query(f"""
                CREATE (:State {{
                    value: {interval_value},
                    first_frame: {frame},
                    created_at: timestamp()
                }})
            """)
            return True
        
        try:
            result = self._execute_with_retry(_create)
            if result:
                self.stats['nodes_created'] += 1
                logger.info(
                    f"[{self.feedback_name}] NEW NODE: {interval_value} @ frame {frame}"
                )
            return result
            
        except GraphOperationError as e:
            raise GraphOperationError(f"Failed to create node: {e}")
    
    def create_action_edge(self,
                          from_value: float,
                          to_value: float,
                          action_discrete: Dict[str, str],
                          frame: int) -> bool:
        """Create action edge with explicit label"""
        try:
            action_parts = [f"{k}_{v}" for k, v in sorted(action_discrete.items())]
            action_label = "__".join(action_parts)
            
            props = [f"{k}: '{v}'" for k, v in action_discrete.items()]
            props.append(f"action_label: '{action_label}'")
            props.append(f"frame: {frame}")
            props.append(f"created_at: timestamp()")
            props_str = ", ".join(props)
            
            def _create_edge():
                self.graph.query(f"""
                    MATCH (from:State {{value: {from_value}}}), 
                          (to:State {{value: {to_value}}})
                    CREATE (from)-[:{action_label} {{{props_str}}}]->(to)
                """)
            
            self._execute_with_retry(_create_edge)
            self.stats['edges_created'] += 1
            
            logger.debug(
                f"[{self.feedback_name}] {from_value} --[{action_label}]--> {to_value}"
            )
            
            return True
            
        except GraphOperationError as e:
            raise GraphOperationError(f"Failed to create edge: {e}")
    
    def get_action_from_frame(self,
                             state_value: float,
                             target_frame: int,
                             tolerance: int = 100,
                             action_names: List[str] = None) -> Optional[Dict[str, str]]:
        """
        GENERIC: Get action taken from state at specific frame
        
        Args:
            state_value: State interval value
            target_frame: Target frame number
            tolerance: Frame tolerance for matching
            action_names: List of action names (from config)
        
        Returns:
            Generic action dictionary or None
        """
        if not action_names:
            logger.warning("No action names provided for generic query")
            return None
        
        # Build dynamic query for generic actions
        action_fields = ", ".join([f"a.{name}" for name in action_names])
        
        def _query():
            result = self.graph.query(f"""
                MATCH (s:State {{value: {state_value}}})-[a]->()
                WHERE abs(a.frame - {target_frame}) <= {tolerance}
                RETURN {action_fields}, a.frame
                ORDER BY abs(a.frame - {target_frame})
                LIMIT 1
            """)
            return result
        
        try:
            result = self._execute_with_retry(_query)
            
            if not result.result_set:
                return None
            
            row = result.result_set[0]
            
            # Build generic action dict
            action = {}
            for i, name in enumerate(action_names):
                action[name] = row[i]
            action['frame'] = row[len(action_names)]
            
            return action
            
        except GraphOperationError:
            return None
    
    def get_tried_actions_count(self, state_value: float) -> int:
        """Count distinct actions tried from this state"""
        def _count():
            result = self.graph.query(f"""
                MATCH (s:State {{value: {state_value}}})-[a]->()
                RETURN count(DISTINCT a.action_label)
            """)
            return result
        
        try:
            result = self._execute_with_retry(_count)
            return result.result_set[0][0] if result.result_set else 0
        except GraphOperationError:
            return 0
    
    def get_statistics(self) -> Dict[str, int]:
        """Get graph statistics"""
        def _get_stats():
            nodes = self.graph.query("MATCH (n:State) RETURN count(n)").result_set[0][0]
            edges = self.graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
            return nodes, edges
        
        try:
            nodes, edges = self._execute_with_retry(_get_stats)
            
            return {
                'nodes': nodes,
                'edges': edges,
                'density': edges / (nodes * nodes) if nodes > 0 else 0.0,
                'avg_degree': edges / nodes if nodes > 0 else 0.0,
                **self.stats
            }
        except GraphOperationError:
            return {**self.stats, 'nodes': 0, 'edges': 0, 'density': 0.0, 'avg_degree': 0.0}


class BrainArchitecture:
    """
    Complete Brain Capacity System V2
    
    NEW FEATURES:
    1. State management integration
    2. Generic query functions
    3. "What Am I?" awareness
    """
    
    def __init__(self, config_path: str):
        """Initialize complete brain architecture"""
        logger.info("="*80)
        logger.info("INITIALIZING BRAIN CAPACITY V2")
        logger.info("="*80)
        
        try:
            self.config = self._load_config(config_path)
            ConfigValidator.validate_config(self.config)
            
            self.action_discretizer = ActionDiscretizer(self.config['actions'])
            self.feedback_discretizer = FeedbackDiscretizer(self.config['feedbacks'])
            
            self.db = self._initialize_database()
            
            self.graphs: Dict[str, KnowledgeGraph] = {}
            self._create_all_graphs()
            
            # NEW: State manager integration
            graph_names = list(self.graphs.keys())
            self.state_manager = StateManager(graph_names)
            
            self.system_stats = {
                'transitions_recorded': 0,
                'queries_executed': 0,
                'errors': 0
            }
            
            logger.info(f"✓ System: {self.config['system_name']}")
            logger.info(f"✓ Actions: {len(self.config['actions'])}")
            logger.info(f"✓ Feedbacks: {len(self.config['feedbacks'])}")
            logger.info(f"✓ Action combinations: {self.action_discretizer.get_max_combinations()}")
            logger.info(f"✓ Knowledge graphs: {len(self.graphs)}")
            logger.info(f"✓ State manager: initialized")
            logger.info("="*80)
            
        except Exception as e:
            raise BrainCapacityError(f"Failed to initialize brain: {e}")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load and parse configuration file"""
        try:
            path = Path(config_path)
            if not path.exists():
                raise ConfigurationError(f"Config file not found: {config_path}")
            
            with open(path, 'r') as f:
                config = json.load(f)
            
            logger.info(f"✓ Configuration loaded from {config_path}")
            return config
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}")
    
    def _initialize_database(self) -> FalkorDB:
        """Initialize database connection with retry logic"""
        sys_config = self.config['system_config']
        
        for attempt in range(sys_config.get('retry_attempts', 3)):
            try:
                db = FalkorDB(
                    host=sys_config['database_host'],
                    port=sys_config['database_port']
                )
                
                db.list_graphs()
                
                logger.info(
                    f"✓ Database connected: {sys_config['database_host']}:{sys_config['database_port']}"
                )
                return db
                
            except Exception as e:
                if attempt < sys_config.get('retry_attempts', 3) - 1:
                    delay = sys_config.get('retry_delay', 1.0)
                    logger.warning(f"Database connection failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    raise DatabaseConnectionError(
                        f"Failed to connect to database after {attempt + 1} attempts: {e}"
                    )
    
    def _create_all_graphs(self):
        """Create all knowledge graphs (one per feedback)"""
        sys_config = self.config['system_config']
        
        for feedback_name in self.config['feedbacks'].keys():
            try:
                self.graphs[feedback_name] = KnowledgeGraph(
                    feedback_name=feedback_name,
                    db=self.db,
                    retry_attempts=sys_config.get('retry_attempts', 3),
                    retry_delay=sys_config.get('retry_delay', 1.0)
                )
            except GraphOperationError as e:
                logger.error(f"Failed to create graph '{feedback_name}': {e}")
                raise BrainCapacityError(f"Graph creation failed: {e}")
    
    def record_transition(self,
                         prev_feedbacks: Dict[str, float],
                         curr_feedbacks: Dict[str, float],
                         action_continuous: Dict[str, float],
                         frame: int) -> bool:
        """Record one transition to knowledge"""
        try:
            InputValidator.validate_frame_number(frame)
            InputValidator.validate_feedbacks(
                prev_feedbacks, 
                self.feedback_discretizer.feedback_names
            )
            InputValidator.validate_feedbacks(
                curr_feedbacks,
                self.feedback_discretizer.feedback_names
            )
            InputValidator.validate_action(
                action_continuous,
                self.action_discretizer.action_names
            )
            
            action_discrete = self.action_discretizer.discretize(action_continuous)
            prev_intervals = self.feedback_discretizer.discretize_all(prev_feedbacks)
            curr_intervals = self.feedback_discretizer.discretize_all(curr_feedbacks)
            
            # Update state manager (NEW)
            self.state_manager.update_state(curr_intervals, frame)
            
            # Record to each graph
            for feedback_name, graph in self.graphs.items():
                if feedback_name not in curr_intervals:
                    continue
                
                prev_value = prev_intervals.get(feedback_name, 0.0)
                curr_value = curr_intervals[feedback_name]
                
                graph.create_node(prev_value, frame - 1)
                graph.create_node(curr_value, frame)
                
                graph.create_action_edge(
                    prev_value, curr_value, action_discrete, frame
                )
            
            self.system_stats['transitions_recorded'] += 1
            
            return True
            
        except (ValidationError, DiscretizationError, GraphOperationError) as e:
            self.system_stats['errors'] += 1
            logger.error(f"Failed to record transition: {e}")
            raise BrainCapacityError(f"Record transition failed: {e}")
    
    def what_am_i(self) -> Dict[str, Any]:
        """
        CRITICAL: "What Am I?" function
        
        Returns complete awareness of current state across ALL graphs
        
        Returns:
            Complete state awareness dictionary
        """
        return self.state_manager.what_am_i()
    
    def query_current_state(self, feedbacks: Dict[str, float]) -> Dict[str, float]:
        """Convert raw feedbacks to intervals"""
        try:
            InputValidator.validate_feedbacks(
                feedbacks,
                self.feedback_discretizer.feedback_names
            )
            
            intervals = self.feedback_discretizer.discretize_all(feedbacks)
            self.system_stats['queries_executed'] += 1
            
            return intervals
            
        except (ValidationError, DiscretizationError) as e:
            self.system_stats['errors'] += 1
            raise BrainCapacityError(f"Query state failed: {e}")
    
    def get_action_from_episode(self,
                                feedbacks: Dict[str, float],
                                episode_frame: int,
                                tolerance: int = 100) -> Optional[Dict[str, str]]:
        """
        GENERIC: Read action from knowledge
        
        Uses generic action names from config
        """
        try:
            intervals = self.query_current_state(feedbacks)
            
            first_feedback = list(intervals.keys())[0]
            if first_feedback not in self.graphs:
                return None
            
            graph = self.graphs[first_feedback]
            
            # GENERIC: Pass action names from config
            action = graph.get_action_from_frame(
                intervals[first_feedback],
                episode_frame,
                tolerance,
                action_names=self.action_discretizer.get_action_names()
            )
            
            return action
            
        except Exception as e:
            logger.warning(f"Failed to get action from episode: {e}")
            return None
    
    def get_max_action_combinations(self) -> int:
        """Return max possible action combinations"""
        return self.action_discretizer.get_max_combinations()
    
    def get_tried_actions_count(self, feedbacks: Dict[str, float]) -> int:
        """Count actions tried from this state"""
        try:
            intervals = self.query_current_state(feedbacks)
            first_feedback = list(intervals.keys())[0]
            
            if first_feedback not in self.graphs:
                return 0
            
            return self.graphs[first_feedback].get_tried_actions_count(
                intervals[first_feedback]
            )
            
        except Exception as e:
            logger.warning(f"Failed to count tried actions: {e}")
            return 0
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        stats = {
            'system': {
                'name': self.config['system_name'],
                'version': self.config.get('version', 'unknown'),
                'actions': len(self.config['actions']),
                'feedbacks': len(self.config['feedbacks']),
                'action_combinations': self.action_discretizer.get_max_combinations(),
                **self.system_stats
            },
            'graphs': {},
            'state': self.state_manager.get_statistics()
        }
        
        for name, graph in self.graphs.items():
            stats['graphs'][name] = graph.get_statistics()
        
        return stats