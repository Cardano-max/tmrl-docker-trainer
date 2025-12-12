"""
INTELLIGENCE: Repeat Episode V3 (Enhanced with Prediction Validation)

FIRST TASK:
"1. Agent performs random actions (record everything)
 2. Next episode: Repeat EXACT sequence from knowledge graphs
 3. VALIDATE: Does prediction match reality?"

KEY CONCEPT:
"After first episode, each state has ONE action to next state"
"""

import logging
from typing import Dict, Optional, Any

from state_manager import StateVector
from intelligence_sensorial import SensorialIntelligence, PredictionResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RepeatEpisodeIntelligence:
    """
    Repeat Episode Intelligence V3
    
    REQUIREMENT:
    "Check where am I → Query graph for action → Predict where I'll go →
     Perform action → Validate: predicted == actual?"
    
    ENHANCED WITH:
    - Prediction before action
    - Validation after action
    - Return codes (0 = match, 1+ = mismatch)
    """
    
    def __init__(self, brain, knowledge, sensorial: SensorialIntelligence):
        """
        Initialize repeat intelligence with prediction validation
        
        Args:
            brain: Brain capacity
            knowledge: Knowledge manager
            sensorial: Sensorial intelligence for validation
        """
        self.brain = brain
        self.knowledge = knowledge
        self.sensorial = sensorial
        
        # Episode tracking
        self.episode_number = 0
        self.episode_start_frame = 0
        self.episode_end_frame = 0
        self.episode_length = 0
        
        # Decision tracking
        self.decisions_made = 0
        self.actions_repeated = 0
        self.actions_failed_prediction = 0
        self.prediction_failures = []
        
        logger.info("[INTELLIGENCE:REPEAT_V3] Initialized with prediction validation")
    
    def decide_action(self,
                     current_feedbacks: Dict[str, float],
                     current_frame: int) -> Optional[tuple[Dict[str, str], StateVector]]:
        """
        Decide action with prediction
        
        PROCESS:
        1. Check where am I (current state)
        2. Query graph: what action exists here?
        3. Predict: where will I go?
        4. Return action AND prediction
        
        Args:
            current_feedbacks: Current sensor values
            current_frame: Current environment frame
        
        Returns:
            (action, predicted_state) or None if no knowledge
        """
        self.decisions_made += 1
        
        # 1. Where am I? (current state)
        current_intervals = self.brain.query_current_state(current_feedbacks)
        current_state = self.brain.state_manager.get_current_state()
        
        if current_state is None:
            logger.warning("[REPEAT_V3] No current state available")
            return None
        
        # 2. What action exists here? (query first graph)
        first_feedback = list(current_intervals.keys())[0]
        if first_feedback not in self.brain.graphs:
            return None
        
        graph = self.brain.graphs[first_feedback]
        state_value = current_intervals[first_feedback]
        
        # Calculate target frame in episode
        if self.episode_start_frame == 0:
            target_frame = current_frame
        else:
            episode_offset = current_frame - self.episode_start_frame
            target_frame = self.episode_start_frame + episode_offset
        
        # Query action from knowledge
        action_discrete = graph.get_action_from_frame(
            state_value,
            target_frame,
            tolerance=100,
            action_names=self.brain.action_discretizer.get_action_names()
        )
        
        if not action_discrete:
            logger.debug(f"[REPEAT_V3] No action found for frame {target_frame}")
            return None
        
        # Remove frame from action dict
        action_discrete = {k: v for k, v in action_discrete.items() if k != 'frame'}
        
        # 3. Predict where we'll go
        predicted_state = self.sensorial.predict_future_state(
            current_state, action_discrete, self.brain
        )
        
        self.actions_repeated += 1
        
        logger.info(
            f"[REPEAT_V3] Frame {current_frame}: "
            f"Action={action_discrete}, "
            f"Predicted={predicted_state.to_vector()}"
        )
        
        return (action_discrete, predicted_state)
    
    def validate_action_result(self,
                               predicted_state: StateVector,
                               actual_feedbacks: Dict[str, float]) -> PredictionResult:
        """
        Validate action result (prediction vs reality)
        
        VALIDATION:
        "If prediction matches reality → return 0
         If different → return 1+ and log"
        
        Args:
            predicted_state: What we predicted would happen
            actual_feedbacks: What actually happened
        
        Returns:
            PredictionResult with validation code
        """
        # Get actual state
        actual_intervals = self.brain.query_current_state(actual_feedbacks)
        actual_state = StateVector(
            graph_positions=actual_intervals,
            timestamp=predicted_state.timestamp,
            frame=predicted_state.frame
        )
        
        # Validate prediction
        result = self.sensorial.validate_prediction(predicted_state, actual_state)
        
        # Track failures
        if result.validation_code > 0:
            self.actions_failed_prediction += 1
            self.prediction_failures.append(result)
            
            logger.warning(
                f"[REPEAT_V3] Prediction failed with code {result.validation_code}: "
                f"{result.deviations}"
            )
        
        return result
    
    def start_episode(self, start_frame: int):
        """Start new episode"""
        self.episode_start_frame = start_frame
        logger.info(f"[REPEAT_V3] Episode started @ frame {start_frame}")
    
    def end_episode(self, end_frame: int):
        """End current episode"""
        self.episode_end_frame = end_frame
        self.episode_length = end_frame - self.episode_start_frame
        self.episode_number += 1
        
        logger.info(
            f"[REPEAT_V3] Episode {self.episode_number} ended @ frame {end_frame} "
            f"(length: {self.episode_length})"
        )
    
    def get_repeat_rate(self) -> float:
        """Get percentage of actions successfully repeated"""
        if self.decisions_made == 0:
            return 0.0
        return (self.actions_repeated / self.decisions_made) * 100.0
    
    def get_prediction_success_rate(self) -> float:
        """Get percentage of predictions that matched reality"""
        if self.actions_repeated == 0:
            return 0.0
        successful = self.actions_repeated - self.actions_failed_prediction
        return (successful / self.actions_repeated) * 100.0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive repeat intelligence statistics"""
        return {
            'episode_number': self.episode_number,
            'episode_length': self.episode_length,
            'decisions_made': self.decisions_made,
            'actions_repeated': self.actions_repeated,
            'actions_failed_prediction': self.actions_failed_prediction,
            'repeat_rate': self.get_repeat_rate(),
            'prediction_success_rate': self.get_prediction_success_rate(),
            'recent_failures': [str(f) for f in self.prediction_failures[-5:]]
        }