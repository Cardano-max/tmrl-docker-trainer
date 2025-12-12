"""
INTELLIGENCE: Sensorial (Prediction Validation) V3

CRITICAL REQUIREMENT:
"Compare brain prediction vs actual sensor feedback"

Example:
- Brain predicts: Go to position 1,2,3 after brake
- Sensors report: Actually at position 2,1,3
- Sensorial intelligence: DETECTS DEVIATION → return code 1+

This is THE core intelligence that validates knowledge
"""

import logging
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict
import time

from state_manager import StateVector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """
    Result of prediction validation
    
    return codes:
    - 0: Prediction matches reality (continue)
    - 1+: Mismatch detected (log, investigate, learn)
    """
    predicted_state: StateVector
    actual_state: StateVector
    matches: bool
    deviations: Dict[str, float]  # graph_name -> deviation amount
    validation_code: int  # 0 = match, 1 = minor, 2 = major, 3 = critical
    timestamp: float
    
    def __repr__(self) -> str:
        if self.matches:
            return f"✓ Prediction CORRECT (code={self.validation_code})"
        else:
            return f"✗ Prediction WRONG (code={self.validation_code}, deviations={self.deviations})"


class SensorialIntelligence:
    """
    Sensorial Intelligence: Brain vs Reality Validation
    
    CONCEPT:
    "Your brain predicts you'll hear me speak.
     Your ears tell you if you actually hear me.
     If mismatch → phone died → sensorial intelligence detected it"
    
    PROCESS:
    1. Agent uses brain (knowledge graphs) to predict future state
    2. Agent performs action
    3. Agent observes actual state (from sensors/environment)
    4. Intelligence compares: predicted == actual?
    5. Returns validation code for system to handle
    """
    
    # Validation return codes ( design)
    CODE_MATCH = 0              # Perfect prediction
    CODE_MINOR_DEVIATION = 1    # Small difference (log)
    CODE_MAJOR_DEVIATION = 2    # Significant difference (investigate)
    CODE_CRITICAL_MISMATCH = 3  # Complete mismatch (learn new knowledge)
    
    def __init__(self, tolerance: float = 0.01):
        """
        Initialize sensorial intelligence
        
        Args:
            tolerance: Acceptable deviation before flagging mismatch
        """
        self.tolerance = tolerance
        
        # Statistics
        self.predictions_made = 0
        self.predictions_correct = 0
        self.predictions_with_minor_deviation = 0
        self.predictions_with_major_deviation = 0
        self.predictions_critical_mismatch = 0
        
        # Detailed tracking
        self.deviations_by_graph = defaultdict(list)
        self.prediction_history = []
        self.max_history = 1000
        
        logger.info("[INTELLIGENCE:SENSORIAL] Initialized")
    
    def predict_future_state(self,
                            current_state: StateVector,
                            action_discrete: Dict[str, str],
                            brain) -> StateVector:
        """
        Predict future state using brain (knowledge graphs)
        
        This is THE prediction that will be validated against reality
        
        Args:
            current_state: Where we are now
            action_discrete: Action we're about to take
            brain: Brain capacity with knowledge graphs
        
        Returns:
            Predicted future state (what brain thinks will happen)
        """
        predicted_positions = {}
        
        for graph_name, current_value in current_state.graph_positions.items():
            # Query graph: "From here, with this action, where do I go?"
            predicted_value = self._query_graph_for_prediction(
                brain, graph_name, current_value, action_discrete
            )
            
            if predicted_value is not None:
                predicted_positions[graph_name] = predicted_value
            else:
                # No knowledge → predict same position (no change)
                predicted_positions[graph_name] = current_value
        
        predicted_state = StateVector(
            graph_positions=predicted_positions,
            timestamp=time.time(),
            frame=current_state.frame + 1
        )
        
        logger.debug(f"[SENSORIAL] Predicted: {predicted_state}")
        
        return predicted_state
    
    def _query_graph_for_prediction(self,
                                    brain,
                                    graph_name: str,
                                    current_value: float,
                                    action_discrete: Dict[str, str]) -> Optional[float]:
        """
        Query specific graph for prediction
        
        Args:
            brain: Brain capacity
            graph_name: Which graph to query
            current_value: Current position in this graph
            action_discrete: Action labels
        
        Returns:
            Predicted next value or None if unknown
        """
        if graph_name not in brain.graphs:
            return None
        
        graph = brain.graphs[graph_name]
        
        # Build action label (explicit edge label)
        action_parts = [f"{k}_{v}" for k, v in sorted(action_discrete.items())]
        action_label = "__".join(action_parts)
        
        try:
            # Query: from current_value, with action_label, what's target?
            result = graph.graph.query(f"""
                MATCH (from:State {{value: {current_value}}})-[:{action_label}]->(to:State)
                RETURN to.value
                LIMIT 1
            """)
            
            if result.result_set:
                predicted_value = result.result_set[0][0]
                logger.debug(
                    f"[SENSORIAL] {graph_name}: "
                    f"{current_value} --[{action_label}]--> {predicted_value}"
                )
                return predicted_value
        except Exception as e:
            logger.debug(f"Prediction query failed for {graph_name}: {e}")
        
        return None
    
    def validate_prediction(self,
                           predicted_state: StateVector,
                           actual_state: StateVector) -> PredictionResult:
        """
        CORE FUNCTION: Validate prediction against reality
        
        requirement:
        "Compare what brain predicted vs what sensors observed"
        
        Args:
            predicted_state: What brain predicted would happen
            actual_state: What actually happened (from sensors)
        
        Returns:
            PredictionResult with validation code
        """
        self.predictions_made += 1
        
        # Compare each graph position
        deviations = {}
        all_match = True
        max_deviation = 0.0
        
        for graph_name in predicted_state.graph_positions:
            predicted_val = predicted_state.graph_positions[graph_name]
            actual_val = actual_state.graph_positions.get(graph_name, predicted_val)
            
            deviation = abs(predicted_val - actual_val)
            
            if deviation > self.tolerance:
                all_match = False
                deviations[graph_name] = deviation
                max_deviation = max(max_deviation, deviation)
                self.deviations_by_graph[graph_name].append(deviation)
        
        # Determine validation code (design)
        if all_match:
            validation_code = self.CODE_MATCH
            self.predictions_correct += 1
            log_level = logging.DEBUG
            symbol = "✓"
        elif max_deviation < 5.0:
            validation_code = self.CODE_MINOR_DEVIATION
            self.predictions_with_minor_deviation += 1
            log_level = logging.INFO
            symbol = "⚠"
        elif max_deviation < 20.0:
            validation_code = self.CODE_MAJOR_DEVIATION
            self.predictions_with_major_deviation += 1
            log_level = logging.WARNING
            symbol = "⚠⚠"
        else:
            validation_code = self.CODE_CRITICAL_MISMATCH
            self.predictions_critical_mismatch += 1
            log_level = logging.ERROR
            symbol = "❌"
        
        result = PredictionResult(
            predicted_state=predicted_state,
            actual_state=actual_state,
            matches=all_match,
            deviations=deviations,
            validation_code=validation_code,
            timestamp=time.time()
        )
        
        # Log based on severity
        logger.log(
            log_level,
            f"[SENSORIAL] {symbol} Code {validation_code}: {result}"
        )
        
        # Store in history
        self.prediction_history.append(result)
        if len(self.prediction_history) > self.max_history:
            self.prediction_history.pop(0)
        
        return result
    
    def get_accuracy(self) -> float:
        """Get prediction accuracy percentage"""
        if self.predictions_made == 0:
            return 0.0
        return (self.predictions_correct / self.predictions_made) * 100.0
    
    def get_recent_predictions(self, n: int = 10) -> list:
        """Get N most recent predictions"""
        return list(reversed(self.prediction_history[-n:]))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive sensorial intelligence statistics"""
        return {
            'predictions_made': self.predictions_made,
            'predictions_correct': self.predictions_correct,
            'minor_deviations': self.predictions_with_minor_deviation,
            'major_deviations': self.predictions_with_major_deviation,
            'critical_mismatches': self.predictions_critical_mismatch,
            'accuracy': self.get_accuracy(),
            'deviations_by_graph': {
                name: {
                    'count': len(devs),
                    'avg_deviation': sum(devs) / len(devs) if devs else 0.0,
                    'max_deviation': max(devs) if devs else 0.0,
                    'min_deviation': min(devs) if devs else 0.0
                }
                for name, devs in self.deviations_by_graph.items()
            },
            'recent_predictions': [str(p) for p in self.get_recent_predictions(5)]
        }
    
    def reset_statistics(self):
        """Reset statistics (keep configuration)"""
        self.predictions_made = 0
        self.predictions_correct = 0
        self.predictions_with_minor_deviation = 0
        self.predictions_with_major_deviation = 0
        self.predictions_critical_mismatch = 0
        self.deviations_by_graph.clear()
        self.prediction_history.clear()
        
        logger.info("[INTELLIGENCE:SENSORIAL] Statistics reset")