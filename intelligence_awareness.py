"""
INTELLIGENCE: AWARENESS (Corrected from "Sensorial Intelligence")

SUPERVISOR'S CORRECTION:
"Sensorial is CAPACITY (ability to sense), NOT intelligence!"
"To see is capacity. What you do with what you see is intelligence."
"This is AWARENESS - comparing knowledge vs reality"

AWARENESS = Type of intelligence that compares:
- Internal model (what knowledge predicts)
- External feedback (what sensors observe)

KEY FEATURES:
1. Prediction from knowledge graphs
2. Reality comparison with configurable tolerance
3. Awareness codes for different mismatch levels
4. Statistics and history tracking
"""

import logging
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

from state_manager import StateVector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AwarenessResult:
    """
    Result of awareness check (knowledge vs reality)
    
    SUPERVISOR'S EXAMPLE:
    "Motor turned twice (what I did)
     Position didn't change - on ice (what happened)
     Awareness detects: prediction was wrong"
    """
    predicted_state: StateVector
    actual_state: StateVector
    matches: bool
    deviations: Dict[str, float]
    awareness_code: int  # 0 = match, 1+ = mismatch levels
    timestamp: float
    
    def __repr__(self) -> str:
        if self.matches:
            return f"✓ Knowledge matches Reality (code={self.awareness_code})"
        else:
            return f"✗ Knowledge ≠ Reality (code={self.awareness_code}, deviations={self.deviations})"


class AwarenessIntelligence:
    """
    Awareness Intelligence: Comparing Internal Model vs External Reality
    
    SUPERVISOR'S FRAMEWORK:
    
    BRAIN CAPACITY (What you have):
    - Sensors (eyes, ears) = ability to receive feedback
    - Motor control = ability to act
    
    KNOWLEDGE (What you think):
    - "If I press brake, I'll go to position X"
    - Stored in knowledge graphs
    
    INTELLIGENCE - AWARENESS (What you do):
    - Compare: "What I thought would happen" vs "What actually happened"
    - Update internal model when mismatch
    - This is AWARENESS
    
    EXAMPLE (Wrong Keyboard Key):
    1. Brain: "Press space" (intention from knowledge)
    2. Finger: Presses key (sensor capacity)
    3. Eye: Sees wrong key (sensor capacity)
    4. Awareness: "I pressed wrong key!" (intelligence comparing)
    5. Action: Press backspace, correct (using awareness)
    """
    
    # Awareness codes (supervisor's return code system)
    CODE_MATCH = 0              # Knowledge matches reality
    CODE_MINOR_DEVIATION = 1    # Small mismatch
    CODE_MAJOR_DEVIATION = 2    # Significant mismatch  
    CODE_CRITICAL_MISMATCH = 3  # Complete wrong
    
    def __init__(self, tolerance: float = 0.01):
        """
        Initialize awareness intelligence
        
        Args:
            tolerance: Acceptable deviation before flagging mismatch
        """
        self.tolerance = tolerance
        
        # Awareness tracking
        self.awareness_checks_performed = 0
        self.knowledge_matched_reality = 0
        self.knowledge_deviated_minor = 0
        self.knowledge_deviated_major = 0
        self.knowledge_completely_wrong = 0
        
        # Detailed tracking
        self.deviations_by_feedback = defaultdict(list)
        self.awareness_history = []
        self.max_history = 1000
        
        logger.info("[INTELLIGENCE:AWARENESS] Initialized")
    
    def predict_from_knowledge(self,
                               current_state: StateVector,
                               action_discrete: Dict[str, str],
                               brain) -> StateVector:
        """
        Predict future state using knowledge (internal model)
        
        SUPERVISOR: "Knowledge tells me: if I press brake, this happens"
        
        Args:
            current_state: Where we are (awareness)
            action_discrete: What we're about to do
            brain: Brain with knowledge graphs
        
        Returns:
            Predicted state (what knowledge thinks will happen)
        """
        predicted_positions = {}
        
        for graph_name, current_value in current_state.graph_positions.items():
            # Query knowledge: "What does my internal model say will happen?"
            predicted_value = self._query_knowledge_graph(
                brain, graph_name, current_value, action_discrete
            )
            
            if predicted_value is not None:
                predicted_positions[graph_name] = predicted_value
            else:
                # No knowledge → predict no change
                predicted_positions[graph_name] = current_value
        
        predicted_state = StateVector(
            graph_positions=predicted_positions,
            timestamp=time.time(),
            frame=current_state.frame + 1
        )
        
        logger.debug(f"[AWARENESS] Knowledge predicts: {predicted_state}")
        
        return predicted_state
    
    def _query_knowledge_graph(self,
                              brain,
                              graph_name: str,
                              current_value: float,
                              action_discrete: Dict[str, str]) -> Optional[float]:
        """
        Query knowledge graph for prediction
        
        SUPERVISOR: "Knowledge is what I think will happen"
        """
        if graph_name not in brain.graphs:
            return None
        
        graph = brain.graphs[graph_name]
        
        # Build action label
        action_parts = [f"{k}_{v}" for k, v in sorted(action_discrete.items())]
        action_label = "__".join(action_parts)
        
        try:
            # Query knowledge: "From here, with this action, where do I go?"
            result = graph.graph.query(f"""
                MATCH (from:State {{value: {current_value}}})-[:{action_label}]->(to:State)
                RETURN to.value
                LIMIT 1
            """)
            
            if result.result_set:
                return result.result_set[0][0]
        except Exception as e:
            logger.debug(f"Knowledge query failed for {graph_name}: {e}")
        
        return None
    
    def check_awareness(self,
                       predicted_state: StateVector,
                       actual_state: StateVector) -> AwarenessResult:
        """
        CORE AWARENESS FUNCTION
        
        Compare internal model (knowledge) vs external reality (feedback)
        
        SUPERVISOR'S EXAMPLE:
        "You press brake (action from knowledge)
         Your ear hears you talk, but I don't hear (feedback)
         Your awareness: 'Phone died!' (detected mismatch)"
        
        Args:
            predicted_state: What knowledge predicted
            actual_state: What sensors observed (reality)
        
        Returns:
            AwarenessResult with awareness code
        """
        self.awareness_checks_performed += 1
        
        # Compare knowledge vs reality for each feedback
        deviations = {}
        all_match = True
        max_deviation = 0.0
        
        for graph_name in predicted_state.graph_positions:
            knowledge_says = predicted_state.graph_positions[graph_name]
            reality_is = actual_state.graph_positions.get(graph_name, knowledge_says)
            
            deviation = abs(knowledge_says - reality_is)
            
            if deviation > self.tolerance:
                all_match = False
                deviations[graph_name] = deviation
                max_deviation = max(max_deviation, deviation)
                self.deviations_by_feedback[graph_name].append(deviation)
        
        # Determine awareness code
        if all_match:
            awareness_code = self.CODE_MATCH
            self.knowledge_matched_reality += 1
            log_level = logging.DEBUG
            symbol = "✓"
        elif max_deviation < 5.0:
            awareness_code = self.CODE_MINOR_DEVIATION
            self.knowledge_deviated_minor += 1
            log_level = logging.INFO
            symbol = "⚠"
        elif max_deviation < 20.0:
            awareness_code = self.CODE_MAJOR_DEVIATION
            self.knowledge_deviated_major += 1
            log_level = logging.WARNING
            symbol = "⚠⚠"
        else:
            awareness_code = self.CODE_CRITICAL_MISMATCH
            self.knowledge_completely_wrong += 1
            log_level = logging.ERROR
            symbol = "❌"
        
        result = AwarenessResult(
            predicted_state=predicted_state,
            actual_state=actual_state,
            matches=all_match,
            deviations=deviations,
            awareness_code=awareness_code,
            timestamp=time.time()
        )
        
        # Log awareness check
        logger.log(
            log_level,
            f"[AWARENESS] {symbol} Code {awareness_code}: {result}"
        )
        
        # Store in history
        self.awareness_history.append(result)
        if len(self.awareness_history) > self.max_history:
            self.awareness_history.pop(0)
        
        return result
    
    def get_awareness_accuracy(self) -> float:
        """
        Get percentage of times knowledge matched reality
        
        SUPERVISOR: "How often is my internal model correct?"
        """
        if self.awareness_checks_performed == 0:
            return 0.0
        return (self.knowledge_matched_reality / self.awareness_checks_performed) * 100.0
    
    def update_knowledge_based_on_awareness(self, result: AwarenessResult):
        """
        Update internal model when awareness detects mismatch
        
        SUPERVISOR: "I update my internal model through your feedback"
        
        This is where learning happens - when awareness says
        "My prediction was wrong, update knowledge"
        """
        if result.awareness_code > 0:
            # Knowledge was wrong, should update
            logger.info(
                f"[AWARENESS] Knowledge needs update: "
                f"predicted {result.predicted_state.to_vector()}, "
                f"reality was {result.actual_state.to_vector()}"
            )
            # Actual update mechanism would go here
    
    def get_recent_awareness_checks(self, count: int = 10) -> list:
        """Get recent awareness check results"""
        return self.awareness_history[-count:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get awareness intelligence statistics"""
        return {
            'awareness_checks': self.awareness_checks_performed,
            'knowledge_correct': self.knowledge_matched_reality,
            'accuracy': self.get_awareness_accuracy(),
            'minor_deviations': self.knowledge_deviated_minor,
            'major_deviations': self.knowledge_deviated_major,
            'critical_mismatches': self.knowledge_completely_wrong,
            'deviations_by_feedback': {
                name: {
                    'count': len(devs),
                    'avg_deviation': sum(devs) / len(devs) if devs else 0.0,
                    'max_deviation': max(devs) if devs else 0.0
                }
                for name, devs in self.deviations_by_feedback.items()
            },
            'recent_checks': [str(a) for a in self.awareness_history[-5:]]
        }
    
    def reset_statistics(self):
        """Reset all statistics"""
        self.awareness_checks_performed = 0
        self.knowledge_matched_reality = 0
        self.knowledge_deviated_minor = 0
        self.knowledge_deviated_major = 0
        self.knowledge_completely_wrong = 0
        self.deviations_by_feedback.clear()
        self.awareness_history.clear()
        logger.info("[AWARENESS] Statistics reset")