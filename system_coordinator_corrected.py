"""
SYSTEM COORDINATOR - CORRECTED V3 (PRODUCTION GRADE)
Complete integration following supervisor's architecture

SUPERVISOR'S FRAMEWORK:
- Brain Capacity: What system CAN do
- Knowledge: What system KNOWS
- Intelligence: How system USES capacity + knowledge

CORRECTIONS APPLIED:
1. Timestamp Manager: Internal time only (no episodes)
2. Awareness Intelligence: Renamed from "sensorial"
3. Clear separation: System vs Environment
"""

import logging
from typing import Dict, Optional, Any
from pathlib import Path

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


class SystemCoordinatorCorrected:
    """
    Complete System Coordinator - Corrected Architecture
    
    SUPERVISOR'S LAYERS:
    
    Layer 1 - BRAIN CAPACITY (What system CAN do):
    - Timestamp Manager (internal time)
    - State Manager (current/previous state)
    - Memory Handler (short/long term)
    - Brain Core (actions/feedbacks)
    
    Layer 2 - KNOWLEDGE (What system KNOWS):
    - Knowledge Graphs (all tried paths)
    - State history
    - Action-outcome mappings
    
    Layer 3 - INTELLIGENCE (How system USES):
    - Awareness (knowledge vs reality)
    - Repeat (query knowledge)
    - Explore (try new actions)
    - Future Constraints (goal validation)
    
    Layer 4 - ENVIRONMENT (Separate):
    - Episodes (training context)
    - Frames (environment counter)
    - Rewards (training signal)
    """
    
    def __init__(self, config_path: str):
        """Initialize complete corrected system"""
        logger.info("="*80)
        logger.info("INITIALIZING CORRECTED SYSTEM V3")
        logger.info("="*80)
        
        try:
            # =================================================================
            # LAYER 1: BRAIN CAPACITY
            # =================================================================
            
            # 1. Brain Core (architecture)
            logger.info("\n[1/9] Initializing Brain Core...")
            self.brain = BrainArchitecture(config_path)
            
            # 2. Timestamp Manager (CORRECTED: internal time only)
            logger.info("\n[2/9] Initializing Timestamp Manager (Internal Time)...")
            self.timestamps = TimestampManager()
            
            # 3. Knowledge Manager
            logger.info("\n[3/9] Initializing Knowledge Manager...")
            self.knowledge = KnowledgeManager(self.brain)
            
            # 4. Episode Recorder
            logger.info("\n[4/9] Initializing Episode Recorder...")
            self.recorder = EpisodeRecorder(self.knowledge, self.timestamps)
            
            # 5. Memory Handler
            logger.info("\n[5/9] Initializing Memory Handler...")
            mem_config = self.brain.config.get('memory_config', {})
            self.memory = MemoryHandler(
                short_term_capacity=mem_config.get('short_term_capacity', 10),
                action_memory_size=mem_config.get('action_memory_size', 1000)
            )
            
            # =================================================================
            # LAYER 3: INTELLIGENCE
            # =================================================================
            
            # 6. Awareness Intelligence (CORRECTED: renamed from sensorial)
            logger.info("\n[6/9] Initializing Awareness Intelligence...")
            intel_config = self.brain.config.get('intelligence_config', {})
            awareness_config = intel_config.get('awareness', {})
            self.intelligence_awareness = AwarenessIntelligence(
                tolerance=awareness_config.get('tolerance', 0.01)
            )
            
            # 7. Intelligence Modules
            logger.info("\n[7/9] Initializing Intelligence Modules...")
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
            logger.info("\n[8/9] Initializing Future Constraints...")
            sim_config = self.brain.config.get('intelligence_config', {}).get('future_constraints', {})
            self.intelligence_constraints = FutureConstraintsIntelligence(
                simulation_mode=sim_config.get('simulation_mode', True)
            )
            
            # 9. Load Constraints from Config
            logger.info("\n[9/9] Loading Constraints from Config...")
            self._load_constraints_from_config()
            
            # Active intelligence
            self.active_intelligence = None
            self.intelligence_mode = None
            
            # Environment interface (SEPARATE from system)
            self.environment_interface = EnvironmentTimeInterface()
            
            logger.info("\n" + "="*80)
            logger.info("✓ CORRECTED SYSTEM V3 READY")
            logger.info("="*80)
            
        except Exception as e:
            raise SystemException(f"System initialization failed: {e}")
    
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
        """Set active intelligence module"""
        if mode == "repeat":
            self.active_intelligence = self.intelligence_repeat
            self.intelligence_mode = "REPEAT_EPISODE"
            logger.info("[SYSTEM] Intelligence mode: REPEAT EPISODE")
            
        elif mode == "explore":
            self.active_intelligence = self.intelligence_explore
            self.intelligence_mode = "EXPLORATION"
            logger.info("[SYSTEM] Intelligence mode: EXPLORATION")
            
        else:
            raise ValueError(f"Unknown intelligence mode: {mode}")
    
    # =========================================================================
    # RECORDING TRANSITIONS
    # =========================================================================
    
    def record_transition(self,
                         prev_feedbacks: Dict[str, float],
                         curr_feedbacks: Dict[str, float],
                         action: Dict[str, float],
                         environment_frame: int,
                         reward: float = 0.0) -> int:
        """
        Record single transition with all validations
        
        SUPERVISOR'S VALIDATION:
        "Return code: 0 = good, 1+ = issues detected"
        
        Args:
            prev_feedbacks: Previous state
            curr_feedbacks: Current state
            action: Action taken
            environment_frame: Environment frame (external)
            reward: Reward received
        
        Returns:
            int: Validation code (0 = success, 1+ = issues)
        """
        try:
            # Record processing iteration (internal)
            self.timestamps.record_processing_iteration()
            
            # Check ranges (range monitoring intelligence)
            violations = self.intelligence_monitor.check_ranges(
                curr_feedbacks, environment_frame
            )
            
            # Record to brain (long-term memory)
            success = self.brain.record_transition(
                prev_feedbacks, curr_feedbacks, action, environment_frame
            )
            
            # Record to memory handler (short-term)
            if success:
                state = self.brain.state_manager.get_current_state()
                self.memory.record_transition(state, action, reward)
            
            # Return validation code
            if not success:
                return 1  # Failed to record
            elif violations:
                return 2  # Range violations detected
            else:
                return 0  # Success
            
        except Exception as e:
            logger.error(f"Failed to record transition: {e}")
            return 3  # Critical error
    
    # =========================================================================
    # DECISION MAKING WITH VALIDATION
    # =========================================================================
    
    def decide_action_with_validation(self,
                                     current_feedbacks: Dict[str, float],
                                     environment_frame: int) -> Optional[Dict[str, Any]]:
        """
        Complete decision cycle with validation
        
        SUPERVISOR'S PROCESS:
        1. Check where am I (current state)
        2. Query knowledge: what action?
        3. Predict: where will I go?
        4. Validate future state (constraints)
        5. Return decision package
        
        Args:
            current_feedbacks: Current sensor values
            environment_frame: Current environment frame
        
        Returns:
            Decision package or None
        """
        if self.active_intelligence is None:
            logger.warning("[SYSTEM] No intelligence mode set")
            return None
        
        try:
            # 1. Where am I? (state awareness)
            current_state = self.brain.state_manager.get_current_state()
            if current_state is None:
                return None
            
            # 2. What action should I take? (query knowledge)
            if self.intelligence_mode == "REPEAT_EPISODE":
                action = self.active_intelligence.decide_action(
                    current_feedbacks, environment_frame
                )
            else:
                action = self.active_intelligence.decide_action(current_feedbacks)
            
            if not action:
                return None
            
            # Get discrete action
            action_continuous = action if isinstance(action, dict) else action[0]
            action_discrete = self.brain.action_discretizer.discretize(action_continuous)
            
            # 3. Predict: where will I go? (awareness intelligence)
            predicted_state = self.intelligence_awareness.predict_from_knowledge(
                current_state, action_discrete, self.brain
            )
            
            # 4. Validate future state (constraints)
            allowed, violations = self.intelligence_constraints.validate_future_state(
                predicted_state, action_discrete
            )
            
            # 5. Return decision package
            return {
                'action_continuous': action_continuous,
                'action_discrete': action_discrete,
                'predicted_state': predicted_state,
                'allowed': allowed,
                'constraint_violations': violations,
                'validation_code': 0 if allowed else 1
            }
            
        except Exception as e:
            logger.error(f"Decision failed: {e}")
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
    # EPISODE MANAGEMENT
    # =========================================================================
    
    def start_episode(self, start_frame: int, episode_number: int = 0):
        """
        Start new episode
        
        NOTE: Episodes are ENVIRONMENT concern, not system
        Supervisor: "Episode means training and environment"
        
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
    # TMRL MEMORY RECORDING
    # =========================================================================
    
    def record_tmrl_memory(self,
                          memory: Any,
                          start_index: int = 0,
                          count: Optional[int] = None) -> Dict[str, Any]:
        """Record transitions from TMRL memory"""
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
            }
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
        print("CORRECTED SYSTEM V3 STATISTICS")
        print("="*80)
        
        print(f"\nSystem: {stats['system']} v{stats['version']}")
        print(f"Intelligence Mode: {stats['intelligence_mode']}")
        
        # Timestamps (CORRECTED: internal only)
        print("\n--- Timestamps (Internal Time) ---")
        ts = stats['timestamps']
        print(f"  System runtime: {ts['system_runtime_seconds']:.2f}s")
        print(f"  Processing iterations: {ts['processing_iterations']}")
        print(f"  Processing rate: {ts['processing_rate_per_sec']:.1f}/sec")
        
        # Brain Capacity
        print("\n--- Brain Capacity ---")
        brain_stats = stats['brain']['system']
        print(f"  Transitions recorded: {brain_stats['transitions_recorded']}")
        print(f"  Queries executed: {brain_stats['queries_executed']}")
        print(f"  Action combinations: {brain_stats['action_combinations']}")
        
        # State Management
        if 'state' in stats['brain']:
            state_stats = stats['brain']['state']
            print(f"\n--- State Management ---")
            print(f"  Graphs tracked: {state_stats['graphs']}")
            print(f"  State transitions: {state_stats['state_transitions']}")
            print(f"  Unique states: {state_stats['unique_states']}")
        
        # Knowledge Graphs
        print("\n--- Knowledge Graphs ---")
        for graph_name, graph_stats in stats['brain']['graphs'].items():
            print(f"  {graph_name}:")
            print(f"    Nodes: {graph_stats['nodes']}")
            print(f"    Edges: {graph_stats['edges']}")
            print(f"    Density: {graph_stats['density']:.6f}")
        
        # Awareness Intelligence (CORRECTED: not sensorial)
        print("\n--- Awareness Intelligence ---")
        awareness = stats['awareness']
        print(f"  Checks performed: {awareness['awareness_checks']}")
        print(f"  Knowledge correct: {awareness['knowledge_correct']}")
        print(f"  Accuracy: {awareness['accuracy']:.1f}%")
        
        # Constraints
        print("\n--- Future Constraints ---")
        const = stats['constraints']
        print(f"  Constraints defined: {const['constraints_defined']}")
        print(f"  Hard constraints: {const['hard_constraints']}")
        print(f"  Total violations: {const['total_violations']}")
        
        # Memory
        print("\n--- Memory ---")
        mem = stats['memory']
        print(f"  Episodes in short-term: {mem['episodes_in_short_term']}")
        print(f"  Total episodes: {mem['episodes_recorded_total']}")
        
        # Intelligence
        if self.intelligence_mode:
            print(f"\n--- Intelligence ({self.intelligence_mode}) ---")
            if 'repeat' in stats['intelligence']:
                rep = stats['intelligence']['repeat']
                print(f"  Decisions made: {rep['decisions_made']}")
                print(f"  Actions repeated: {rep['actions_repeated']}")
        
        print("\n" + "="*80)