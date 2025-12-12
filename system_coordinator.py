"""
SYSTEM COORDINATOR V3
Complete integration with all requirements

NEW FEATURES:
1. Dual timestamp system (agent + environment)
2. Sensorial intelligence (prediction validation)
3. Future constraints (goal-oriented behavior)
4. Enhanced repeat intelligence with prediction
5. Return codes for validation (0 = match, 1+ = issues)
"""

import logging
from typing import Dict, Optional, Any, Tuple

from brain_capacity_v2 import BrainArchitecture
from knowledge_manager import KnowledgeManager, EpisodeRecorder
from intelligence_repeat_v3 import RepeatEpisodeIntelligence
from intelligence_explore import ExplorationIntelligence
from intelligence_monitor import RangeMonitorIntelligence
from intelligence_sensorial import SensorialIntelligence
from intelligence_future_constraints import (
    FutureConstraintsIntelligence, 
    ConstraintType,
    ConstraintFactory
)
from state_manager import StateManager, StateVector
from memory_handler import MemoryHandler
from timestamp_manager import TimestampManager, TimestampInfo
from exceptions import SystemException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemCoordinator:
    """
    Main system coordinator V3
    
    COMPLETE INTEGRATION OF ALL REQUIREMENTS:
    - Brain Capacity (architecture + state)
    - Dual Timestamps (agent + environment)
    - Sensorial Intelligence (prediction validation)
    - Future Constraints (goal validation)
    - Memory Handler (short/long-term)
    - All intelligence modules
    """
    
    def __init__(self, config_path: str):
        """Initialize complete system V3"""
        logger.info("="*80)
        logger.info("INITIALIZING COMPLETE SYSTEM V3")
        logger.info("="*80)
        
        try:
            # 1. Brain Capacity (architecture + state)
            logger.info("\n[1/9] Initializing Brain Capacity V2...")
            self.brain = BrainArchitecture(config_path)
            
            # 2. Timestamp Manager (NEW)
            logger.info("\n[2/9] Initializing Timestamp Manager...")
            self.timestamps = TimestampManager()
            
            # 3. Knowledge Manager
            logger.info("\n[3/9] Initializing Knowledge Manager...")
            self.knowledge = KnowledgeManager(self.brain)
            
            # 4. Episode Recorder
            logger.info("\n[4/9] Initializing Episode Recorder...")
            self.recorder = EpisodeRecorder(self.knowledge)
            # V3: Link timestamp manager to recorder for frame tracking
            self.recorder.set_timestamp_manager(self.timestamps)
            
            # 5. Memory Handler
            logger.info("\n[5/9] Initializing Memory Handler...")
            mem_config = self.brain.config.get('memory_config', {})
            self.memory = MemoryHandler(
                short_term_capacity=mem_config.get('short_term_capacity', 10),
                action_memory_size=mem_config.get('action_memory_size', 1000)
            )
            
            # 6. Sensorial Intelligence (NEW - CRITICAL)
            logger.info("\n[6/9] Initializing Sensorial Intelligence...")
            intel_config = self.brain.config.get('intelligence_config', {})
            sensorial_config = intel_config.get('sensorial', {})
            self.intelligence_sensorial = SensorialIntelligence(
                tolerance=sensorial_config.get('tolerance', 0.01)
            )
            
            # 7. Intelligence Modules
            logger.info("\n[7/9] Initializing Intelligence Modules...")
            self.intelligence_repeat = RepeatEpisodeIntelligence(
                self.brain, self.knowledge, self.intelligence_sensorial
            )
            self.intelligence_explore = ExplorationIntelligence(
                self.brain, self.knowledge
            )
            self.intelligence_monitor = RangeMonitorIntelligence(
                self.brain.config['feedbacks']
            )
            
            # 8. Future Constraints Intelligence (NEW)
            logger.info("\n[8/9] Initializing Future Constraints Intelligence...")
            sim_config = self.brain.config.get('simulation_config', {})
            self.intelligence_constraints = FutureConstraintsIntelligence(
                simulation_mode=sim_config.get('simulation_mode', True)
            )
            
            # 9. Load default constraints from config
            logger.info("\n[9/9] Loading Constraints...")
            self._load_constraints_from_config()
            
            # Active intelligence
            self.active_intelligence = None
            self.intelligence_mode = None
            
            logger.info("\n" + "="*80)
            logger.info("✓ SYSTEM V3 READY")
            logger.info("="*80)
            
        except Exception as e:
            raise SystemException(f"System V3 initialization failed: {e}")
    
    def _load_constraints_from_config(self):
        """Load constraints from config (hard/soft based on constraint_type)"""
        for feedback_name, feedback_config in self.brain.config['feedbacks'].items():
            constraint_type_str = feedback_config.get('constraint_type', 'soft')
            constraint_type = (
                ConstraintType.HARD if constraint_type_str == 'hard' 
                else ConstraintType.SOFT
            )
            
            min_val, max_val = feedback_config['expected_range']
            
            name, ctype, check_func, desc = ConstraintFactory.create_range_constraint(
                feedback_name, min_val, max_val, constraint_type,
                f"{feedback_name} range constraint from config"
            )
            
            self.intelligence_constraints.add_constraint(
                name, ctype, check_func, desc
            )
    
    def set_intelligence_mode(self, mode: str):
        """Set active intelligence module"""
        if mode == "repeat":
            self.active_intelligence = self.intelligence_repeat
            self.intelligence_mode = "REPEAT_EPISODE"
            logger.info("[SYSTEM] Intelligence mode: REPEAT EPISODE (with prediction)")
            
        elif mode == "explore":
            self.active_intelligence = self.intelligence_explore
            self.intelligence_mode = "EXPLORATION"
            logger.info("[SYSTEM] Intelligence mode: EXPLORATION")
            
        elif mode == "monitor":
            self.active_intelligence = self.intelligence_monitor
            self.intelligence_mode = "RANGE_MONITOR"
            logger.info("[SYSTEM] Intelligence mode: RANGE MONITOR")
            
        else:
            raise ValueError(f"Unknown intelligence mode: {mode}")
    
    def record_transition(self,
                         prev_feedbacks: Dict[str, float],
                         curr_feedbacks: Dict[str, float],
                         action: Dict[str, float],
                         environment_frame: int,
                         reward: float = 0.0) -> int:
        """
        Record single transition with full validation chain
        
        VALIDATION CHAIN:
        1. Range monitoring (config vs actual)
        2. Record to brain (long-term memory)
        3. Record to memory handler (short-term)
        4. Update timestamps
        
        Args:
            prev_feedbacks: Previous state
            curr_feedbacks: Current state
            action: Action taken
            environment_frame: Environment frame counter
            reward: Reward received
        
        Returns:
            Validation code (0 = all good, 1+ = issues)
        """
        validation_code = 0
        
        try:
            # Get timestamps
            timestamp_info = self.timestamps.get_current_timestamps(environment_frame)
            
            # 1. Range monitoring (intelligence)
            violations = self.intelligence_monitor.check_ranges(
                curr_feedbacks, environment_frame
            )
            if violations:
                validation_code = max(validation_code, 1)
            
            # 2. Record to brain (long-term memory - FalkorDB)
            success = self.brain.record_transition(
                prev_feedbacks, curr_feedbacks, action, environment_frame
            )
            
            if not success:
                validation_code = max(validation_code, 2)
            
            # 3. Record to memory handler (short-term)
            if success:
                state = self.brain.state_manager.get_current_state()
                self.memory.record_transition(state, action, reward)
            
            # 4. Update timestamp tracking
            self.timestamps.record_frame(environment_frame)
            
            return validation_code
            
        except Exception as e:
            logger.error(f"Failed to record transition: {e}")
            return 99  # Error code
    
    def decide_action_with_validation(self,
                                     current_feedbacks: Dict[str, float],
                                     environment_frame: int) -> Optional[Dict[str, Any]]:
        """
        COMPLETE DECISION CYCLE:
        
        1. Check where am I (current state)
        2. Query: what action to take?
        3. Predict: where will I go?
        4. Validate future state (constraints)
        5. Return decision package
        
        Returns:
            {
                'action_discrete': action to take,
                'predicted_state': where we'll go,
                'validation_code': 0 = safe, 1+ = issues,
                'allowed': True/False (constraints),
                'constraint_violations': list of violations
            }
        """
        if self.active_intelligence is None:
            logger.warning("[SYSTEM] No intelligence mode set")
            return None
        
        try:
            # Get timestamp info
            timestamp_info = self.timestamps.get_current_timestamps(environment_frame)
            
            # STEP 1-3: Intelligence decides action + predicts future
            if self.intelligence_mode == "REPEAT_EPISODE":
                result = self.intelligence_repeat.decide_action(
                    current_feedbacks, environment_frame
                )
                
                if result is None:
                    return None
                
                action_discrete, predicted_state = result
            else:
                # Other intelligence modes
                action_discrete = self.active_intelligence.decide_action(
                    current_feedbacks
                )
                
                if action_discrete is None:
                    return None
                
                # Predict future state
                current_state = self.brain.state_manager.get_current_state()
                predicted_state = self.intelligence_sensorial.predict_future_state(
                    current_state, action_discrete, self.brain
                )
            
            # STEP 4: Validate future state (constraints)
            allowed, constraint_violations = (
                self.intelligence_constraints.validate_future_state(
                    predicted_state, action_discrete
                )
            )
            
            # STEP 5: Package decision
            decision = {
                'action_discrete': action_discrete,
                'predicted_state': predicted_state,
                'validation_code': 0 if allowed else 1,
                'allowed': allowed,
                'constraint_violations': constraint_violations,
                'timestamp_info': timestamp_info
            }
            
            return decision
            
        except Exception as e:
            logger.error(f"Decision with validation failed: {e}")
            return None
    
    def validate_action_result(self,
                               predicted_state: StateVector,
                               actual_feedbacks: Dict[str, float]) -> int:
        """
        VALIDATION AFTER ACTION:
        
        "Compare predicted state vs actual state"
        "Return 0 if match, 1+ if mismatch"
        
        Args:
            predicted_state: What we predicted
            actual_feedbacks: What actually happened
        
        Returns:
            Validation code (0 = match, 1+ = deviation level)
        """
        result = self.intelligence_repeat.validate_action_result(
            predicted_state, actual_feedbacks
        )
        
        return result.validation_code
    
    def record_tmrl_memory(self,
                          memory: Any,
                          start_index: int = 0,
                          count: Optional[int] = None) -> Dict[str, Any]:
        """Record transitions from TMRL memory"""
        return self.recorder.record_tmrl_memory(memory, start_index, count)
    
    def what_am_i(self) -> Dict[str, Any]:
        """
        CRITICAL: "What Am I?" function (enhanced with timestamps)
        
        Returns complete system awareness:
        - Brain state (positions in graphs)
        - Timestamps (agent + environment)
        - Memory status
        - Intelligence mode
        - Monitoring status
        """
        brain_state = self.brain.what_am_i()
        memory_stats = self.memory.get_statistics()
        monitor_stats = self.intelligence_monitor.get_statistics()
        sensorial_stats = self.intelligence_sensorial.get_statistics()
        timestamp_stats = self.timestamps.get_statistics()
        
        awareness = {
            'brain_state': brain_state,
            'timestamps': timestamp_stats,
            'memory': {
                'last_episode': memory_stats['last_episode'],
                'short_term_capacity': memory_stats['episodes_in_short_term']
            },
            'intelligence_mode': self.intelligence_mode,
            'monitoring': {
                'range_violations': monitor_stats['total_violations'],
                'prediction_accuracy': sensorial_stats['accuracy']
            }
        }
        
        return awareness
    
    def start_episode(self, start_frame: int, episode_number: int = 0):
        """
        Start new episode (updates ALL subsystems)
        
        Updates:
        - Timestamp manager (episode tracking)
        - Memory handler (episode buffer)
        - Repeat intelligence (episode sync)
        """
        # Timestamp manager
        self.timestamps.start_new_episode(episode_number, start_frame)
        
        # Memory handler
        self.memory.start_episode(episode_number, start_frame)
        
        # Repeat intelligence
        if self.intelligence_mode == "REPEAT_EPISODE":
            self.intelligence_repeat.start_episode(start_frame)
        
        logger.info(
            f"[SYSTEM] Episode {episode_number} started @ frame {start_frame} "
            f"(agent_time={self.timestamps.get_agent_runtime():.2f}s)"
        )
    
    def end_episode(self, end_frame: int):
        """End current episode"""
        # Memory handler
        episode = self.memory.end_episode(end_frame)
        
        # Repeat intelligence
        if self.intelligence_mode == "REPEAT_EPISODE":
            self.intelligence_repeat.end_episode(end_frame)
        
        logger.info(
            f"[SYSTEM] Episode ended: {len(episode.actions)} actions recorded "
            f"(agent_time={self.timestamps.get_agent_runtime():.2f}s)"
        )
    
    def get_exploration_status(self, feedbacks: Dict[str, float]) -> Dict[str, Any]:
        """Get exploration status for current state"""
        return self.knowledge.get_exploration_status(feedbacks)
    
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get complete system statistics (all modules)"""
        stats = {
            'system': self.brain.config['system_name'],
            'version': self.brain.config.get('version', 'unknown'),
            'intelligence_mode': self.intelligence_mode,
            'brain': self.brain.get_system_statistics(),
            'timestamps': self.timestamps.get_statistics(),
            'knowledge': self.knowledge.get_knowledge_summary(),
            'memory': self.memory.get_statistics(),
            'monitoring': self.intelligence_monitor.get_statistics(),
            'sensorial': self.intelligence_sensorial.get_statistics(),
            'constraints': self.intelligence_constraints.get_statistics(),
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
        print("SYSTEM V3 STATISTICS")
        print("="*80)
        
        print(f"\nSystem: {stats['system']} v{stats['version']}")
        print(f"Intelligence Mode: {stats['intelligence_mode']}")
        
        # Timestamps
        print("\n--- Timestamps ---")
        ts = stats['timestamps']
        print(f"  Agent runtime: {ts['agent']['runtime_seconds']:.2f}s")
        print(f"  Total episodes: {ts['agent']['total_episodes']}")
        print(f"  Total frames: {ts['agent']['total_frames']}")
        print(f"  Current episode: {ts['episode']['number']}")
        print(f"  Episode runtime: {ts['episode']['runtime_seconds']:.2f}s")
        
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
            print(f"  Current state: {state_stats['current_state']}")
        
        # Knowledge Graphs
        print("\n--- Knowledge Graphs ---")
        for graph_name, graph_stats in stats['brain']['graphs'].items():
            print(f"  {graph_name}:")
            print(f"    Nodes: {graph_stats['nodes']}")
            print(f"    Edges: {graph_stats['edges']}")
            print(f"    Density: {graph_stats['density']:.6f}")
            print(f"    Avg degree: {graph_stats['avg_degree']:.2f}")
        
        # Sensorial Intelligence (NEW)
        print("\n--- Sensorial Intelligence ---")
        sens_stats = stats['sensorial']
        print(f"  Predictions made: {sens_stats['predictions_made']}")
        print(f"  Predictions correct: {sens_stats['predictions_correct']}")
        print(f"  Accuracy: {sens_stats['accuracy']:.1f}%")
        print(f"  Minor deviations: {sens_stats['minor_deviations']}")
        print(f"  Major deviations: {sens_stats['major_deviations']}")
        print(f"  Critical mismatches: {sens_stats['critical_mismatches']}")
        
        # Future Constraints (NEW)
        print("\n--- Future Constraints ---")
        const_stats = stats['constraints']
        print(f"  Constraints defined: {const_stats['constraints_defined']}")
        print(f"  Hard constraints: {const_stats['hard_constraints']}")
        print(f"  Soft constraints: {const_stats['soft_constraints']}")
        print(f"  Total violations: {const_stats['total_violations']}")
        print(f"  Hard violations blocked: {const_stats['hard_violations_blocked']}")
        print(f"  Simulation mode: {const_stats['simulation_mode']}")
        
        # Memory
        print("\n--- Memory ---")
        mem_stats = stats['memory']
        print(f"  Episodes in short-term: {mem_stats['episodes_in_short_term']}")
        print(f"  Total episodes: {mem_stats['episodes_recorded_total']}")
        print(f"  Last episode: {mem_stats['last_episode']['number']} ({mem_stats['last_episode']['length']} actions)")
        
        # Intelligence
        if self.intelligence_mode:
            print(f"\n--- Intelligence ({self.intelligence_mode}) ---")
            if 'repeat' in stats['intelligence']:
                rep_stats = stats['intelligence']['repeat']
                print(f"  Episode: {rep_stats['episode_number']}")
                print(f"  Decisions made: {rep_stats['decisions_made']}")
                print(f"  Actions repeated: {rep_stats['actions_repeated']}")
                print(f"  Prediction success rate: {rep_stats['prediction_success_rate']:.1f}%")
        
        print("\n" + "="*80)