"""
SYSTEM COORDINATOR - PRODUCTION GRADE V4
Complete integration following supervisor's architecture

SUPERVISOR'S FRAMEWORK:
Layer 1 - BRAIN CAPACITY: What system CAN do
Layer 2 - KNOWLEDGE: What system KNOWS  
Layer 3 - INTELLIGENCE: How system USES capacity + knowledge
Layer 4 - ENVIRONMENT: Separate concern (not part of system)

KEY FEATURES:
1. Disjoint action validation
2. Environment-agnostic design
3. Complete decision cycle with awareness
4. Explainable reasoning paths
"""

import logging
from typing import Dict, Optional, Any, List
from pathlib import Path
from abc import ABC, abstractmethod

# Brain Capacity
from brain_core import BrainArchitecture
from timestamp_manager_corrected import TimestampManager, EnvironmentTimeInterface
from state_manager import StateManager, StateVector
from memory_handler import MemoryHandler

# Knowledge
from knowledge_manager import KnowledgeManager, EpisodeRecorder

# Intelligence
from intelligence_awareness import AwarenessIntelligence
from intelligence_repeat import RepeatEpisodeIntelligence
from intelligence_explore import ExplorationIntelligence
from intelligence_monitor import RangeMonitorIntelligence
from intelligence_future_constraints import (
    FutureConstraintsIntelligence, ConstraintType, ConstraintFactory
)

from exceptions import SystemException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnvironmentAdapter(ABC):
    """
    Abstract interface for environment interaction
    
    SUPERVISOR: "System should be environment agnostic"
    "Episodes are environment concern, not system"
    
    This adapter allows the system to work with ANY environment
    by abstracting the data extraction logic.
    """
    
    @abstractmethod
    def extract_feedbacks(self, observation: Any) -> Dict[str, float]:
        """Extract feedback values from environment observation"""
        pass
    
    @abstractmethod
    def extract_actions(self, action_data: Any) -> Dict[str, float]:
        """Extract action values from environment action format"""
        pass
    
    @abstractmethod
    def get_frame(self, observation: Any) -> int:
        """Get current frame/timestep from environment"""
        pass


class GenericEnvironmentAdapter(EnvironmentAdapter):
    """
    Generic adapter that expects data in standard format
    
    Use this when feedbacks/actions are already in dict format.
    """
    
    def __init__(self, feedback_names: List[str], action_names: List[str]):
        self.feedback_names = feedback_names
        self.action_names = action_names
    
    def extract_feedbacks(self, observation: Dict[str, float]) -> Dict[str, float]:
        """Pass through dict format"""
        return {k: v for k, v in observation.items() if k in self.feedback_names}
    
    def extract_actions(self, action_data: Dict[str, float]) -> Dict[str, float]:
        """Pass through dict format"""
        return {k: v for k, v in action_data.items() if k in self.action_names}
    
    def get_frame(self, observation: Any) -> int:
        """Extract frame from observation dict or return 0"""
        if isinstance(observation, dict) and 'frame' in observation:
            return observation['frame']
        return 0


class TMRLEnvironmentAdapter(EnvironmentAdapter):
    """
    Adapter for TMRL (TrackMania) environment
    
    IMPORTANT: This is ONLY for testing purposes.
    The core system remains environment-agnostic.
    """
    
    def __init__(self, feedback_names: List[str], action_names: List[str]):
        self.feedback_names = feedback_names
        self.action_names = action_names
    
    def extract_feedbacks(self, observation: Any) -> Dict[str, float]:
        """Extract from TMRL observation format"""
        try:
            if hasattr(observation, '__getitem__'):
                # TMRL format: [speed, lidar_0, lidar_1, lidar_2, ...]
                feedbacks = {}
                if len(observation) > 0:
                    feedbacks['speed'] = float(observation[0])
                if len(observation) > 1:
                    feedbacks['lidar_0'] = float(observation[1])
                if len(observation) > 2:
                    feedbacks['lidar_1'] = float(observation[2])
                if len(observation) > 3:
                    feedbacks['lidar_2'] = float(observation[3])
                return feedbacks
        except Exception as e:
            logger.warning(f"TMRL feedback extraction failed: {e}")
        
        return {}
    
    def extract_actions(self, action_data: Any) -> Dict[str, float]:
        """Extract from TMRL action format"""
        try:
            if hasattr(action_data, '__getitem__'):
                # TMRL format: [gas, brake, steering]
                actions = {}
                if len(action_data) > 0:
                    actions['gas'] = float(action_data[0])
                if len(action_data) > 1:
                    actions['brake'] = float(action_data[1])
                if len(action_data) > 2:
                    actions['steering'] = float(action_data[2])
                return actions
        except Exception as e:
            logger.warning(f"TMRL action extraction failed: {e}")
        
        return {}
    
    def get_frame(self, observation: Any) -> int:
        """TMRL doesn't provide frame in observation"""
        return 0


class DecisionPackage:
    """
    Structured decision output with explainability
    
    SUPERVISOR: "Every decision is traceable through graph paths"
    """
    
    def __init__(self,
                 action_continuous: Optional[Dict[str, float]],
                 action_discrete: Dict[str, str],
                 current_state: StateVector,
                 predicted_state: Optional[StateVector],
                 allowed: bool,
                 constraint_violations: List[str],
                 reasoning: Dict[str, Any]):
        self.action_continuous = action_continuous
        self.action_discrete = action_discrete
        self.current_state = current_state
        self.predicted_state = predicted_state
        self.allowed = allowed
        self.constraint_violations = constraint_violations
        self.reasoning = reasoning
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'action_continuous': self.action_continuous,
            'action_discrete': self.action_discrete,
            'current_state': self.current_state.to_dict() if self.current_state else None,
            'predicted_state': self.predicted_state.to_dict() if self.predicted_state else None,
            'allowed': self.allowed,
            'constraint_violations': self.constraint_violations,
            'reasoning': self.reasoning
        }
    
    def explain(self) -> str:
        """Generate human-readable explanation"""
        lines = [
            "=== DECISION EXPLANATION ===",
            f"Action: {self.action_discrete}",
            f"Valid: {self.allowed}",
            f"Current State: {self.current_state}",
            f"Predicted State: {self.predicted_state}",
        ]
        
        if self.constraint_violations:
            lines.append(f"Violations: {self.constraint_violations}")
        
        for key, value in self.reasoning.items():
            lines.append(f"{key}: {value}")
        
        return "\n".join(lines)


class SystemCoordinatorCorrected:
    """
    Complete System Coordinator - Production Grade V4
    
    SUPERVISOR'S ARCHITECTURE:
    
    Layer 1 - BRAIN CAPACITY (What system CAN do):
    - Timestamp Manager (internal time)
    - State Manager (current/previous state)
    - Memory Handler (short/long term)
    - Brain Core (actions/feedbacks with disjoint filtering)
    
    Layer 2 - KNOWLEDGE (What system KNOWS):
    - Knowledge Graphs (all tried paths)
    - State history
    - Action-outcome mappings
    - Prior knowledge (from config)
    - Acquired knowledge (from experience)
    
    Layer 3 - INTELLIGENCE (How system USES):
    - Awareness (knowledge vs reality)
    - Repeat (query knowledge)
    - Explore (try new actions)
    - Future Constraints (goal validation)
    - Monitor (range checking)
    
    Layer 4 - ENVIRONMENT (Separate):
    - Handled via EnvironmentAdapter
    - Episodes (training context)
    - Frames (environment counter)
    """
    
    def __init__(self, config_path: str):
        """Initialize complete corrected system"""
        logger.info("="*80)
        logger.info("INITIALIZING REAL INTELLIGENCE SYSTEM V4")
        logger.info("="*80)
        
        try:
            # =================================================================
            # LAYER 1: BRAIN CAPACITY
            # =================================================================
            
            # 1. Brain Core (architecture with disjoint filtering)
            logger.info("\n[1/10] Initializing Brain Core...")
            self.brain = BrainArchitecture(config_path)
            
            # 2. Timestamp Manager (CORRECTED: internal time only)
            logger.info("\n[2/10] Initializing Timestamp Manager (Internal Time)...")
            self.timestamps = TimestampManager()
            
            # 3. Knowledge Manager
            logger.info("\n[3/10] Initializing Knowledge Manager...")
            self.knowledge = KnowledgeManager(self.brain)
            
            # 4. Episode Recorder
            logger.info("\n[4/10] Initializing Episode Recorder...")
            self.recorder = EpisodeRecorder(self.knowledge, self.timestamps)
            
            # 5. Memory Handler
            logger.info("\n[5/10] Initializing Memory Handler...")
            mem_config = self.brain.config.get('memory_config', {})
            self.memory = MemoryHandler(
                short_term_capacity=mem_config.get('short_term_capacity', 10),
                action_memory_size=mem_config.get('action_memory_size', 1000)
            )
            
            # =================================================================
            # LAYER 3: INTELLIGENCE
            # =================================================================
            
            # 6. Awareness Intelligence (renamed from sensorial)
            logger.info("\n[6/10] Initializing Awareness Intelligence...")
            intel_config = self.brain.config.get('intelligence_config', {})
            awareness_config = intel_config.get('awareness', {})
            self.intelligence_awareness = AwarenessIntelligence(
                tolerance=awareness_config.get('tolerance', 0.01)
            )
            
            # 7. Intelligence Modules
            logger.info("\n[7/10] Initializing Intelligence Modules...")
            self.intelligence_repeat = RepeatEpisodeIntelligence(
                self.brain, self.knowledge, self.intelligence_awareness
            )
            self.intelligence_explore = ExplorationIntelligence(
                self.brain, self.knowledge
            )
            self.intelligence_monitor = RangeMonitorIntelligence(
                self.brain.config['feedbacks']
            )
            
            # 8. Future Constraints Intelligence
            logger.info("\n[8/10] Initializing Future Constraints...")
            sim_config = intel_config.get('future_constraints', {})
            self.intelligence_constraints = FutureConstraintsIntelligence(
                simulation_mode=sim_config.get('simulation_mode', True)
            )
            
            # 9. Load Constraints from Config
            logger.info("\n[9/10] Loading Constraints from Config...")
            self._load_constraints_from_config()
            
            # 10. Environment Adapter (default to generic)
            logger.info("\n[10/10] Initializing Environment Adapter...")
            self._setup_environment_adapter()
            
            # Active intelligence
            self.active_intelligence = None
            self.intelligence_mode = None
            
            # Environment interface (SEPARATE from system)
            self.environment_interface = EnvironmentTimeInterface()
            
            # Statistics
            self.decisions_made = 0
            self.successful_decisions = 0
            
            logger.info("\n" + "="*80)
            logger.info("✓ REAL INTELLIGENCE SYSTEM V4 READY")
            logger.info(f"✓ Valid action combinations: {self.brain.get_max_action_combinations()}")
            logger.info(f"✓ Disjoint pairs: {self.brain.action_discretizer.get_disjoint_pairs()}")
            logger.info("="*80)
            
        except Exception as e:
            raise SystemException(f"System initialization failed: {e}")
    
    def _setup_environment_adapter(self):
        """Setup environment adapter based on config or default"""
        feedback_names = list(self.brain.config['feedbacks'].keys())
        action_names = list(self.brain.config['actions'].keys())
        
        # Default to generic adapter
        self.environment_adapter = GenericEnvironmentAdapter(
            feedback_names, action_names
        )
        logger.info(f"[ENV] Generic adapter initialized")
    
    def set_environment_adapter(self, adapter: EnvironmentAdapter):
        """
        Set custom environment adapter
        
        SUPERVISOR: "System should be environment agnostic"
        This allows plugging in different environments.
        """
        self.environment_adapter = adapter
        logger.info(f"[ENV] Custom adapter set: {type(adapter).__name__}")
    
    def use_tmrl_adapter(self):
        """Convenience method to switch to TMRL adapter"""
        feedback_names = list(self.brain.config['feedbacks'].keys())
        action_names = list(self.brain.config['actions'].keys())
        self.environment_adapter = TMRLEnvironmentAdapter(
            feedback_names, action_names
        )
        logger.info("[ENV] TMRL adapter enabled")
    
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    
    def _load_constraints_from_config(self):
        """Load constraints from configuration"""
        feedbacks = self.brain.config['feedbacks']
        
        for name, config in feedbacks.items():
            constraint_type_str = config.get('constraint_type', 'soft')
            constraint_type = (
                ConstraintType.HARD if constraint_type_str == 'hard' 
                else ConstraintType.SOFT
            )
            
            constraint_params = ConstraintFactory.create_range_constraint(
                graph_name=name,
                min_val=config['expected_range'][0],
                max_val=config['expected_range'][1],
                constraint_type=constraint_type,
                description=f"{name} range constraint from config"
            )
            
            self.intelligence_constraints.add_constraint(*constraint_params)
    
    # =========================================================================
    # INTELLIGENCE MODE MANAGEMENT
    # =========================================================================
    
    def set_intelligence_mode(self, mode: str):
        """
        Set active intelligence module
        
        Modes:
        - "repeat": Repeat learned episode sequences
        - "explore": Try untried actions
        - "hybrid": Combine repeat + explore
        """
        if mode == "repeat":
            self.active_intelligence = self.intelligence_repeat
            self.intelligence_mode = "REPEAT_EPISODE"
        elif mode == "explore":
            self.active_intelligence = self.intelligence_explore
            self.intelligence_mode = "EXPLORATION"
        elif mode == "hybrid":
            # TODO: Implement hybrid intelligence
            self.active_intelligence = self.intelligence_repeat
            self.intelligence_mode = "HYBRID"
        else:
            logger.warning(f"Unknown intelligence mode: {mode}")
            return
        
        logger.info(f"[SYSTEM] Intelligence mode: {self.intelligence_mode}")
    
    # =========================================================================
    # CORE DECISION PROCESS (SUPERVISOR'S FRAMEWORK)
    # =========================================================================
    
    def decide_action(self,
                     current_feedbacks: Dict[str, float],
                     environment_frame: int = 0) -> Optional[DecisionPackage]:
        """
        SUPERVISOR'S DECISION PROCESS:
        
        1. Check where am I (state awareness)
        2. Query knowledge for action
        3. Predict: where will I go (use knowledge)
        4. Validate constraints
        5. Return decision package with explainability
        
        Args:
            current_feedbacks: Current sensor values
            environment_frame: Current environment frame
        
        Returns:
            DecisionPackage with full explainability or None
        """
        self.decisions_made += 1
        reasoning = {'steps': []}
        
        if self.active_intelligence is None:
            logger.warning("[SYSTEM] No intelligence mode set")
            return None
        
        try:
            # =====================================================
            # STEP 1: WHERE AM I? (State Awareness)
            # =====================================================
            reasoning['steps'].append("1. Checking current state...")
            
            current_intervals = self.brain.query_current_state(current_feedbacks)
            current_state = self.brain.state_manager.get_current_state()
            
            if current_state is None:
                # Create initial state
                self.brain.state_manager.update_state(current_intervals, environment_frame)
                current_state = self.brain.state_manager.get_current_state()
            
            reasoning['current_state'] = current_state.to_dict()
            reasoning['steps'].append(f"   State: {current_state}")
            
            # =====================================================
            # STEP 2: QUERY KNOWLEDGE FOR ACTION
            # =====================================================
            reasoning['steps'].append("2. Querying knowledge for action...")
            
            if self.intelligence_mode == "REPEAT_EPISODE":
                action = self.active_intelligence.decide_action(
                    current_feedbacks, environment_frame
                )
            else:
                action = self.active_intelligence.decide_action(current_feedbacks)
            
            if not action:
                reasoning['steps'].append("   No action found in knowledge")
                reasoning['decision'] = "NO_ACTION"
                return None
            
            # Handle different return types from intelligence modules
            # RepeatEpisodeIntelligence returns (action_discrete, predicted_state) tuple
            # Other intelligences may return continuous action dict
            if isinstance(action, tuple):
                # Tuple: (action_discrete, predicted_state) from Repeat intelligence
                action_discrete = action[0]
                # action is already discrete (strings like 'NONE', 'HIGH')
                action_continuous = None  # Not available from repeat intelligence
            else:
                # Dict: continuous action from other intelligences
                action_continuous = action
                action_discrete = self.brain.action_discretizer.discretize(action_continuous)
            
            # Validate disjoint rules
            is_valid_action = self.brain.action_discretizer.is_valid_action(action_discrete)
            reasoning['action'] = action_discrete
            reasoning['action_valid'] = is_valid_action
            reasoning['steps'].append(f"   Action: {action_discrete}")
            reasoning['steps'].append(f"   Valid (disjoint check): {is_valid_action}")
            
            if not is_valid_action:
                reasoning['steps'].append("   WARNING: Action violates disjoint rules!")
            
            # =====================================================
            # STEP 3: PREDICT WHERE WILL I GO (Awareness)
            # =====================================================
            reasoning['steps'].append("3. Predicting future state from knowledge...")
            
            predicted_state = self.intelligence_awareness.predict_from_knowledge(
                current_state, action_discrete, self.brain
            )
            
            reasoning['predicted_state'] = predicted_state.to_dict() if predicted_state else None
            reasoning['steps'].append(f"   Predicted: {predicted_state}")
            
            # =====================================================
            # STEP 4: VALIDATE CONSTRAINTS
            # =====================================================
            reasoning['steps'].append("4. Validating future constraints...")
            
            allowed, violations = self.intelligence_constraints.validate_future_state(
                predicted_state, action_discrete
            )
            
            reasoning['allowed'] = allowed
            reasoning['violations'] = violations
            reasoning['steps'].append(f"   Allowed: {allowed}")
            if violations:
                reasoning['steps'].append(f"   Violations: {violations}")
            
            # =====================================================
            # STEP 5: BUILD DECISION PACKAGE
            # =====================================================
            self.successful_decisions += 1
            
            return DecisionPackage(
                action_continuous=action_continuous,
                action_discrete=action_discrete,
                current_state=current_state,
                predicted_state=predicted_state,
                allowed=allowed,
                constraint_violations=violations,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Decision failed: {e}")
            reasoning['error'] = str(e)
            return None
    
    def validate_action_result(self,
                               predicted_state: StateVector,
                               actual_feedbacks: Dict[str, float]) -> int:
        """
        Validate action result (awareness check)
        
        SUPERVISOR: "Compare knowledge prediction vs sensor reality"
        
        Args:
            predicted_state: What knowledge predicted
            actual_feedbacks: What sensors observed
        
        Returns:
            int: Awareness code (0 = match, 1+ = mismatch)
        """
        # Use brain's query method to get actual state
        actual_intervals = self.brain.query_current_state(actual_feedbacks)
        
        actual_state = StateVector(
            graph_positions=actual_intervals,
            timestamp=predicted_state.timestamp,
            frame=predicted_state.frame
        )
        
        # Check awareness (knowledge vs reality)
        result = self.intelligence_awareness.check_awareness(
            predicted_state, actual_state
        )
        
        return result.awareness_code
    
    # =========================================================================
    # ENVIRONMENT-AGNOSTIC DATA RECORDING
    # =========================================================================
    
    def record_transition_generic(self,
                                  prev_observation: Any,
                                  curr_observation: Any,
                                  action: Any,
                                  frame: int) -> bool:
        """
        Record transition using environment adapter
        
        This is the ENVIRONMENT-AGNOSTIC entry point.
        The adapter handles format conversion.
        """
        try:
            prev_feedbacks = self.environment_adapter.extract_feedbacks(prev_observation)
            curr_feedbacks = self.environment_adapter.extract_feedbacks(curr_observation)
            actions = self.environment_adapter.extract_actions(action)
            
            return self.brain.record_transition(
                prev_feedbacks, curr_feedbacks, actions, frame
            )
        except Exception as e:
            logger.error(f"Generic transition recording failed: {e}")
            return False
    
    def record_transition(self,
                         prev_feedbacks: Dict[str, float],
                         curr_feedbacks: Dict[str, float],
                         action_continuous: Dict[str, float],
                         frame: int) -> bool:
        """
        Direct transition recording (dict format)
        
        Use this when data is already in the correct format.
        """
        return self.brain.record_transition(
            prev_feedbacks, curr_feedbacks, action_continuous, frame
        )
    
    # =========================================================================
    # EPISODE MANAGEMENT
    # =========================================================================
    
    def start_episode(self, start_frame: int, episode_number: int = 0):
        """
        Start new episode
        
        NOTE: Episodes are ENVIRONMENT concern, not system
        SUPERVISOR: "Episode means training and environment"
        
        We track this for coordination, but it's not core system state
        """
        # Memory handler
        self.memory.start_episode(episode_number, start_frame)
        
        # Repeat intelligence
        if self.intelligence_mode == "REPEAT_EPISODE":
            self.intelligence_repeat.start_episode(start_frame)
        
        logger.info(f"[SYSTEM] Episode {episode_number} started @ frame {start_frame}")
    
    def end_episode(self, end_frame: int):
        """End current episode"""
        # Memory handler
        episode = self.memory.end_episode(end_frame)
        
        # Repeat intelligence
        if self.intelligence_mode == "REPEAT_EPISODE":
            self.intelligence_repeat.end_episode(end_frame)
        
        logger.info(f"[SYSTEM] Episode ended: {len(episode.actions)} actions")
    
    # =========================================================================
    # TMRL MEMORY RECORDING (For Testing Only)
    # =========================================================================
    
    def record_tmrl_memory(self,
                          memory: Any,
                          start_index: int = 0,
                          count: Optional[int] = None) -> Dict[str, Any]:
        """
        Record transitions from TMRL memory
        
        NOTE: This is for testing with TMRL environment only.
        The core system remains environment-agnostic.
        """
        return self.recorder.record_tmrl_memory(memory, start_index, count)
    
    # =========================================================================
    # SELF-AWARENESS
    # =========================================================================
    
    def what_am_i(self) -> Dict[str, Any]:
        """
        CRITICAL: "What Am I?" function
        
        SUPERVISOR: "System knows where it is across all graphs"
        
        Returns complete system awareness
        """
        brain_state = self.brain.what_am_i()
        memory_stats = self.memory.get_statistics()
        awareness_stats = self.intelligence_awareness.get_statistics()
        timestamp_stats = self.timestamps.get_statistics()
        
        awareness = {
            'brain_state': brain_state,
            'timestamps': timestamp_stats,
            'memory': {
                'last_episode': memory_stats['last_episode'],
                'short_term_capacity': memory_stats['episodes_in_short_term']
            },
            'intelligence_mode': self.intelligence_mode,
            'awareness': {
                'checks_performed': awareness_stats['awareness_checks'],
                'accuracy': awareness_stats['accuracy']
            },
            'disjoint_pairs': self.brain.action_discretizer.get_disjoint_pairs(),
            'valid_combinations': self.brain.get_max_action_combinations()
        }
        
        return awareness
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get complete system statistics"""
        stats = {
            'system': self.brain.config['system_name'],
            'version': self.brain.config.get('version', 'unknown'),
            'intelligence_mode': self.intelligence_mode,
            'decisions': {
                'total': self.decisions_made,
                'successful': self.successful_decisions,
                'success_rate': (self.successful_decisions / self.decisions_made * 100) 
                               if self.decisions_made > 0 else 0.0
            },
            'brain': self.brain.get_system_statistics(),
            'knowledge': self.knowledge.get_knowledge_summary(),
            'memory': self.memory.get_statistics(),
            'timestamps': self.timestamps.get_statistics(),
            'awareness': self.intelligence_awareness.get_statistics(),
            'constraints': self.intelligence_constraints.get_statistics(),
            'monitoring': self.intelligence_monitor.get_statistics(),
            'intelligence': {}
        }
        
        if self.intelligence_mode == "REPEAT_EPISODE":
            stats['intelligence']['repeat'] = self.intelligence_repeat.get_statistics()
        elif self.intelligence_mode == "EXPLORATION":
            stats['intelligence']['explore'] = self.intelligence_explore.get_statistics()
        
        return stats
    
    def print_statistics(self):
        """Print formatted statistics"""
        stats = self.get_comprehensive_statistics()
        
        print("\n" + "="*80)
        print("REAL INTELLIGENCE SYSTEM V4 STATISTICS")
        print("="*80)
        
        print(f"\nSystem: {stats['system']} v{stats['version']}")
        print(f"Intelligence Mode: {stats['intelligence_mode']}")
        
        # Decisions
        print("\n--- Decisions ---")
        d = stats['decisions']
        print(f"  Total decisions: {d['total']}")
        print(f"  Successful: {d['successful']}")
        print(f"  Success rate: {d['success_rate']:.1f}%")
        
        # Timestamps (CORRECTED: internal only)
        print("\n--- Timestamps (Internal Time) ---")
        ts = stats['timestamps']
        print(f"  System runtime: {ts['system_runtime_seconds']:.2f}s")
        print(f"  Processing iterations: {ts['processing_iterations']}")
        print(f"  Processing rate: {ts['processing_rate_per_sec']:.1f}/sec")
        
        # Brain Capacity
        print("\n--- Brain Capacity ---")
        brain = stats['brain']['system']
        print(f"  Transitions recorded: {brain['transitions_recorded']}")
        print(f"  Queries executed: {brain['queries_executed']}")
        print(f"  Disjoint pairs: {brain['disjoint_pairs']}")
        print(f"  Raw combinations: {brain['raw_combinations']}")
        print(f"  Valid combinations: {brain['valid_combinations']}")
        
        # State Management
        print("\n--- State Management ---")
        state = stats['brain']['state_manager']
        print(f"  Graphs tracked: {state['graphs']}")
        print(f"  State transitions: {state['state_transitions']}")
        print(f"  Unique states: {state['unique_states']}")
        
        # Knowledge Graphs
        print("\n--- Knowledge Graphs ---")
        for name, graph in stats['brain']['graphs'].items():
            print(f"  {name}:")
            print(f"    Nodes: {graph['nodes']}")
            print(f"    Edges: {graph['edges']}")
            print(f"    Density: {graph['density']:.6f}")
        
        # Awareness Intelligence
        print("\n--- Awareness Intelligence ---")
        awareness = stats['awareness']
        print(f"  Checks performed: {awareness['awareness_checks']}")
        print(f"  Knowledge correct: {awareness['knowledge_correct']}")
        print(f"  Accuracy: {awareness['accuracy']:.1f}%")
        
        # Future Constraints
        print("\n--- Future Constraints ---")
        constraints = stats['constraints']
        print(f"  Constraints defined: {constraints['total_constraints']}")
        print(f"  Hard constraints: {constraints['hard_constraints']}")
        print(f"  Total violations: {constraints.get('total_violations', 0)}")
        
        # Memory
        print("\n--- Memory ---")
        mem = stats['memory']
        print(f"  Episodes in short-term: {mem['episodes_in_short_term']}")
        print(f"  Total episodes: {mem['episodes_recorded_total']}")
        
        # Intelligence specific
        if stats['intelligence']:
            print(f"\n--- Intelligence ({stats['intelligence_mode']}) ---")
            for key, value in stats['intelligence'].items():
                if isinstance(value, dict):
                    for k, v in value.items():
                        print(f"  {k}: {v}")
                else:
                    print(f"  {key}: {value}")
        
        print("\n" + "="*80)