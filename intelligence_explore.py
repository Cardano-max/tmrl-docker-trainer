"""
INTELLIGENCE: Exploration

Second intelligence module - uses knowledge to explore efficiently
Tries untried actions from current state
"""

import logging
from typing import Dict, Optional, List
import random

from brain_capacity import BrainArchitecture
from knowledge_manager import KnowledgeManager
from exceptions import IntelligenceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExplorationIntelligence:
    """
    Intelligence that explores by trying untried actions
    
    INTELLIGENCE DECISION:
    - Given current state, find which actions haven't been tried
    - Try first untried action
    - If all tried, move to different state (via random action)
    """
    
    def __init__(self,
                 brain: BrainArchitecture,
                 knowledge: KnowledgeManager):
        """
        Initialize exploration intelligence
        
        Args:
            brain: Brain architecture instance
            knowledge: Knowledge manager instance
        """
        self.brain = brain
        self.knowledge = knowledge
        
        # Decision statistics
        self.decisions_made = 0
        self.untried_actions_taken = 0
        self.random_actions_taken = 0
        
        logger.info("[INTELLIGENCE:EXPLORE] Initialized")
    
    def decide_action(self, current_feedbacks: Dict[str, float]) -> Optional[Dict[str, str]]:
        """
        CORE INTELLIGENCE DECISION
        
        Decision Logic:
        1. Where am I? (get current state intervals)
        2. How many actions have I tried from here?
        3. If not all tried, return first untried
        4. If all tried, return None (trigger random to move to new state)
        
        Args:
            current_feedbacks: Current state feedbacks
        
        Returns:
            Discrete action to execute, or None for random
        """
        self.decisions_made += 1
        
        try:
            # Get exploration status
            status = self.knowledge.get_exploration_status(current_feedbacks)
            
            if status['fully_explored']:
                logger.debug(
                    f"[INTELLIGENCE:EXPLORE] State fully explored "
                    f"({status['actions_tried']}/{status['actions_tried']}), "
                    f"need random to move"
                )
                self.random_actions_taken += 1
                return None
            
            # Get all possible actions
            all_actions = self.brain.action_discretizer.all_combinations
            
            # Get tried actions from first graph
            intervals = status['state_intervals']
            first_feedback = list(intervals.keys())[0]
            graph = self.brain.graphs[first_feedback]
            state_value = intervals[first_feedback]
            
            # Query tried action labels
            tried_labels = set()
            try:
                result = graph.graph.query(f"""
                    MATCH (s:State {{value: {state_value}}})-[a]->()
                    RETURN DISTINCT a.action_label
                """)
                tried_labels = {row[0] for row in result.result_set}
            except Exception as e:
                logger.warning(f"Failed to query tried actions: {e}")
            
            # Find untried action
            for action_combo in all_actions:
                # Create action label
                action_parts = [f"{k}_{v}" for k, v in sorted(action_combo.items())]
                action_label = "__".join(action_parts)
                
                if action_label not in tried_labels:
                    self.untried_actions_taken += 1
                    logger.debug(
                        f"[INTELLIGENCE:EXPLORE] Untried action found: {action_combo}"
                    )
                    return action_combo
            
            # All actions tried (shouldn't reach here if status check works)
            logger.warning("[INTELLIGENCE:EXPLORE] All actions tried but status said otherwise")
            self.random_actions_taken += 1
            return None
            
        except Exception as e:
            logger.error(f"[INTELLIGENCE:EXPLORE] Decision failed: {e}")
            self.random_actions_taken += 1
            return None
    
    def get_statistics(self) -> Dict[str, any]:
        """Get intelligence statistics"""
        return {
            'decisions_made': self.decisions_made,
            'untried_actions_taken': self.untried_actions_taken,
            'random_actions_taken': self.random_actions_taken,
            'exploration_rate': (self.untried_actions_taken / self.decisions_made * 100)
                               if self.decisions_made > 0 else 0
        }
    
    def reset(self):
        """Reset intelligence state"""
        self.decisions_made = 0
        self.untried_actions_taken = 0
        self.random_actions_taken = 0
        
        logger.info("[INTELLIGENCE:EXPLORE] Reset")