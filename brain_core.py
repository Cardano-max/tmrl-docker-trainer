"""
BRAIN CAPACITY V3 - With Disjoint Action Filtering

SUPERVISOR'S FRAMEWORK:
- Brain Capacity = What system CAN do
- NOT intelligence, just raw capabilities

CRITICAL UPDATES (v3):
1. Disjoint action filtering (from latest meeting)
2. Generic query functions (not hardcoded gas/brake/steering)
3. Integration with StateManager for "What Am I?"
4. State-aware operations
5. Returns valid action combinations only

DISJOINT ACTIONS (Supervisor's requirement):
- Actions that cannot occur simultaneously
- Example: brake disjoint accelerate, left disjoint right
- These are filtered from combination generation
"""

import json
import logging
import math
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from pathlib import Path
from itertools import product
from functools import lru_cache
from falkordb import FalkorDB

from exceptions import (
    ConfigurationError, BrainCapacityError, DiscretizationError,
    GraphOperationError, DatabaseConnectionError, ValidationError
)
from validators import ConfigValidator, InputValidator
from state_manager import StateManager, StateVector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DisjointActionValidator:
    """
    Validates and filters disjoint action combinations
    
    SUPERVISOR'S ONTOLOGY CONCEPT:
    "Disjoint is an expression from ontology - it means having no elements in common"
    "If action is disjoint, isolate from combinations"
    
    Example:
    - brake disjoint accelerate → cannot both be active (non-NONE)
    - left disjoint right → cannot steer both directions
    """
    
    def __init__(self, actions_config: Dict[str, Any]):
        """Initialize disjoint validator from config"""
        self.actions_config = actions_config
        self.disjoint_pairs: Set[Tuple[str, str]] = set()
        
        # Extract disjoint declarations from each action
        for action_name, action_config in actions_config.items():
            disjoint_list = action_config.get('disjoint', [])
            for disjoint_action in disjoint_list:
                if disjoint_action in actions_config:
                    # Store as sorted tuple to avoid duplicates
                    pair = tuple(sorted([action_name, disjoint_action]))
                    self.disjoint_pairs.add(pair)
        
        logger.info(f"[BRAIN] Disjoint pairs loaded: {self.disjoint_pairs}")
    
    def is_valid_combination(self, combination: Dict[str, str]) -> bool:
        """
        Check if action combination is valid (no disjoint violations)
        
        SUPERVISOR'S RULE:
        "Every time they're all for all the positions that have brake 
        and accelerate in the same combination, this is eliminated"
        
        Args:
            combination: Dict of {action_name: action_label}
        
        Returns:
            True if valid (no disjoint violations)
        """
        for action1, action2 in self.disjoint_pairs:
            label1 = combination.get(action1, 'NONE')
            label2 = combination.get(action2, 'NONE')
            
            # Both actions are active (non-NONE) = disjoint violation
            # SUPERVISOR: "Or you're breaking or you're accelerating"
            if label1 != 'NONE' and label2 != 'NONE':
                return False
        
        return True
    
    def filter_combinations(self, 
                           all_combinations: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Filter out invalid combinations based on disjoint rules
        
        Args:
            all_combinations: All possible combinations
        
        Returns:
            Valid combinations only
        """
        valid = [c for c in all_combinations if self.is_valid_combination(c)]
        
        filtered_count = len(all_combinations) - len(valid)
        logger.info(
            f"[BRAIN] Disjoint filter: {filtered_count} invalid combinations removed, "
            f"{len(valid)} valid combinations remain"
        )
        
        return valid
    
    def get_disjoint_pairs(self) -> List[Tuple[str, str]]:
        """Get list of disjoint action pairs"""
        return list(self.disjoint_pairs)


class ActionDiscretizer:
    """
    Discretizes continuous actions to bins with caching
    
    SUPERVISOR'S NOTE:
    "Actions are CAPACITY - what system CAN do"
    """
    
    def __init__(self, actions_config: Dict[str, Any]):
        """Initialize from validated configuration"""
        try:
            self.config = actions_config
            self.action_names = sorted(list(actions_config.keys()))
            
            # Initialize disjoint validator
            self.disjoint_validator = DisjointActionValidator(actions_config)
            
            # Pre-compute all combinations (including invalid)
            self._all_raw_combinations = self._generate_all_combinations()
            
            # Filter to valid combinations only
            self.all_combinations = self.disjoint_validator.filter_combinations(
                self._all_raw_combinations
            )
            
            # Create lookup maps for fast discretization
            self._bin_lookup = self._create_bin_lookup()
            
            logger.info(
                f"[BRAIN] Action Discretizer initialized: "
                f"{len(self.action_names)} actions, "
                f"{len(self.all_combinations)} valid combinations "
                f"(filtered from {len(self._all_raw_combinations)} raw)"
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
        """Generate all possible action combinations (before disjoint filtering)"""
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
    
    def is_valid_action(self, discrete_actions: Dict[str, str]) -> bool:
        """Check if action combination is valid (respects disjoint rules)"""
        return self.disjoint_validator.is_valid_combination(discrete_actions)
    
    def get_max_combinations(self) -> int:
        """Get total number of valid action combinations"""
        return len(self.all_combinations)
    
    def get_raw_combinations_count(self) -> int:
        """Get total number of raw combinations (before filtering)"""
        return len(self._all_raw_combinations)
    
    def get_combination_index(self, discrete_actions: Dict[str, str]) -> int:
        """Get index of action combination"""
        try:
            return self.all_combinations.index(discrete_actions)
        except ValueError:
            return -1
    
    def get_action_names(self) -> List[str]:
        """Get list of action names (generic)"""
        return self.action_names.copy()
    
    def get_disjoint_pairs(self) -> List[Tuple[str, str]]:
        """Get list of disjoint action pairs"""
        return self.disjoint_validator.get_disjoint_pairs()
    
    def get_untried_actions(self, 
                           tried_combinations: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Get valid actions not yet tried
        
        SUPERVISOR: "Exploration - try untried actions from current state"
        """
        tried_set = {tuple(sorted(c.items())) for c in tried_combinations}
        untried = [
            c for c in self.all_combinations 
            if tuple(sorted(c.items())) not in tried_set
        ]
        return untried


class FeedbackDiscretizer:
    """
    Discretizes continuous feedback to intervals with caching
    
    SUPERVISOR'S NOTE:
    "Feedback is CAPACITY - what sensors receive"
    "Intervals not exact values - discrete bins for continuous feedback"
    """
    
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
    """
    Single knowledge graph for one feedback type
    
    SUPERVISOR'S FRAMEWORK:
    "Knowledge Graphs: One graph per feedback dimension"
    "Stores state transitions and actions taken"
    """
    
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
                logger.debug(
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
    
    def get_tried_action_labels(self, state_value: float) -> List[str]:
        """Get distinct action labels tried from this state"""
        def _get_labels():
            result = self.graph.query(f"""
                MATCH (s:State {{value: {state_value}}})-[a]->()
                RETURN DISTINCT a.action_label
            """)
            return result
        
        try:
            result = self._execute_with_retry(_get_labels)
            return [row[0] for row in result.result_set] if result.result_set else []
        except GraphOperationError:
            return []
    
    def query_transition(self,
                        from_value: float,
                        action_label: str) -> Optional[float]:
        """
        Query knowledge: "From state X, with action Y, where do I go?"
        
        SUPERVISOR: "Knowledge tells me: if I press brake, this happens"
        """
        def _query():
            result = self.graph.query(f"""
                MATCH (from:State {{value: {from_value}}})-[:{action_label}]->(to:State)
                RETURN to.value
                LIMIT 1
            """)
            return result
        
        try:
            result = self._execute_with_retry(_query)
            if result.result_set:
                return result.result_set[0][0]
            return None
        except GraphOperationError:
            return None
    
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
    Complete Brain Capacity System V3
    
    SUPERVISOR'S FRAMEWORK:
    "Brain Capacity = What system CAN do (NOT intelligence)"
    "To see is capacity. What you do with what you see is intelligence."
    
    FEATURES:
    1. Disjoint action filtering (from latest meeting)
    2. State management integration
    3. Generic query functions
    4. "What Am I?" awareness
    """
    
    def __init__(self, config_path: str):
        """Initialize complete brain architecture"""
        logger.info("="*80)
        logger.info("INITIALIZING BRAIN CAPACITY V3")
        logger.info("="*80)
        
        try:
            self.config = self._load_config(config_path)
            ConfigValidator.validate_config(self.config)
            
            # Action discretizer with disjoint filtering
            self.action_discretizer = ActionDiscretizer(self.config['actions'])
            self.feedback_discretizer = FeedbackDiscretizer(self.config['feedbacks'])
            
            self.db = self._initialize_database()
            
            self.graphs: Dict[str, KnowledgeGraph] = {}
            self._create_all_graphs()
            
            # State manager integration
            graph_names = list(self.graphs.keys())
            self.state_manager = StateManager(graph_names)
            
            self.system_stats = {
                'transitions_recorded': 0,
                'queries_executed': 0,
                'errors': 0
            }
            
            # Log disjoint info
            disjoint_pairs = self.action_discretizer.get_disjoint_pairs()
            
            logger.info(f"✓ System: {self.config['system_name']}")
            logger.info(f"✓ Actions: {len(self.config['actions'])}")
            logger.info(f"✓ Feedbacks: {len(self.config['feedbacks'])}")
            logger.info(f"✓ Disjoint pairs: {disjoint_pairs}")
            logger.info(f"✓ Raw combinations: {self.action_discretizer.get_raw_combinations_count()}")
            logger.info(f"✓ Valid combinations: {self.action_discretizer.get_max_combinations()}")
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
            
            # Validate action is valid (respects disjoint rules)
            if not self.action_discretizer.is_valid_action(action_discrete):
                logger.warning(f"[BRAIN] Invalid action (disjoint violation): {action_discrete}")
                # Still record for learning, but flag it
            
            prev_intervals = self.feedback_discretizer.discretize_all(prev_feedbacks)
            curr_intervals = self.feedback_discretizer.discretize_all(curr_feedbacks)
            
            # Update state manager
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
        
        SUPERVISOR: "System knows where it is across all graphs"
        
        Returns complete awareness of current state across ALL graphs
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
    
    def get_valid_combinations(self) -> List[Dict[str, str]]:
        """Get all valid action combinations (disjoint-filtered)"""
        return self.action_discretizer.all_combinations.copy()
    
    def get_max_action_combinations(self) -> int:
        """Return max possible valid action combinations"""
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
    
    def get_untried_actions(self, feedbacks: Dict[str, float]) -> List[Dict[str, str]]:
        """
        Get valid actions not yet tried from this state
        
        SUPERVISOR: "Exploration - try untried actions"
        """
        try:
            intervals = self.query_current_state(feedbacks)
            first_feedback = list(intervals.keys())[0]
            
            if first_feedback not in self.graphs:
                return self.get_valid_combinations()
            
            graph = self.graphs[first_feedback]
            tried_labels = graph.get_tried_action_labels(intervals[first_feedback])
            
            # Filter out tried from valid combinations
            untried = []
            for combo in self.action_discretizer.all_combinations:
                action_parts = [f"{k}_{v}" for k, v in sorted(combo.items())]
                action_label = "__".join(action_parts)
                if action_label not in tried_labels:
                    untried.append(combo)
            
            return untried
            
        except Exception as e:
            logger.warning(f"Failed to get untried actions: {e}")
            return self.get_valid_combinations()
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        stats = {
            'system': {
                'name': self.config['system_name'],
                'version': self.config.get('version', 'unknown'),
                'actions': len(self.config['actions']),
                'feedbacks': len(self.config['feedbacks']),
                'disjoint_pairs': self.action_discretizer.get_disjoint_pairs(),
                'raw_combinations': self.action_discretizer.get_raw_combinations_count(),
                'valid_combinations': self.action_discretizer.get_max_combinations(),
                **self.system_stats
            },
            'graphs': {},
            'state_manager': self.state_manager.get_statistics()
        }
        
        for name, graph in self.graphs.items():
            stats['graphs'][name] = graph.get_statistics()
        
        return stats