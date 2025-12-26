"""
INTELLIGENCE: Exploration

Second intelligence module - uses knowledge to explore efficiently
Tries untried VALID actions from current state

SUPERVISOR'S FRAMEWORK:
"Exploration - try untried actions from current state"

KEY FEATURES:
1. Respects disjoint action rules
2. Prioritizes unexplored areas
3. Environment-agnostic
"""

import logging
import random
from typing import Dict, Optional, List, Any

from brain_core import BrainArchitecture
from knowledge_manager import KnowledgeManager
from exceptions import IntelligenceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExplorationIntelligence:
    """
    Intelligence that explores by trying untried actions
    
    INTELLIGENCE DECISION:
    - Query: "What actions have I NOT tried from here?"
    - Return: Valid untried action
    
    CRITICAL: Only returns actions that respect disjoint rules
    """
    
    def __init__(self, 
                 brain: BrainArchitecture,
                 knowledge: KnowledgeManager):
        """
        Initialize exploration intelligence
        
        Args:
            brain: BrainArchitecture instance
            knowledge: KnowledgeManager instance
        """
        self.brain = brain
        self.knowledge = knowledge
        
        # Statistics
        self.exploration_decisions = 0
        self.untried_actions_found = 0
        self.random_selections = 0
        
        logger.info("[INTELLIGENCE:EXPLORE] Initialized")
    
    def decide_action(self, 
                     feedbacks: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Decide action through exploration
        
        Process:
        1. Get current state
        2. Query knowledge: what actions tried from here?
        3. Find VALID untried actions (respecting disjoint)
        4. Return random untried action
        
        Args:
            feedbacks: Current feedback values
        
        Returns:
            Action dictionary or None
        """
        self.exploration_decisions += 1
        
        try:
            # Get untried valid actions
            untried = self.brain.get_untried_actions(feedbacks)
            
            if not untried:
                logger.debug("[EXPLORE] All valid actions tried from this state")
                return None
            
            self.untried_actions_found += 1
            
            # Random selection from untried
            selected = random.choice(untried)
            self.random_selections += 1
            
            # Convert labels to continuous values
            action_continuous = self._labels_to_continuous(selected)
            
            logger.debug(f"[EXPLORE] Selected untried action: {selected}")
            
            return action_continuous
            
        except Exception as e:
            logger.error(f"Exploration decision failed: {e}")
            return None
    
    def _labels_to_continuous(self, 
                              action_labels: Dict[str, str]) -> Dict[str, float]:
        """
        Convert action labels to continuous values
        
        Uses midpoint of each bin as continuous value
        """
        continuous = {}
        
        for action_name, label in action_labels.items():
            action_config = self.brain.config['actions'].get(action_name, {})
            bins = action_config.get('bins', [])
            
            # Find bin with this label
            for bin_info in bins:
                if bin_info['label'] == label:
                    # Use midpoint
                    continuous[action_name] = (bin_info['min'] + bin_info['max']) / 2
                    break
            else:
                # Default to 0 if not found
                continuous[action_name] = 0.0
        
        return continuous
    
    def get_exploration_status(self, 
                               feedbacks: Dict[str, float]) -> Dict[str, Any]:
        """
        Get exploration status for current state
        
        Returns info about tried vs untried actions
        """
        try:
            # Query knowledge
            knowledge_info = self.knowledge.query_knowledge(feedbacks)
            
            # Get untried actions
            untried = self.brain.get_untried_actions(feedbacks)
            
            valid_total = self.brain.get_max_action_combinations()
            tried_count = valid_total - len(untried)
            
            return {
                'state': knowledge_info.get('state_intervals', {}),
                'total_valid_actions': valid_total,
                'tried_actions': tried_count,
                'untried_actions': len(untried),
                'exploration_percent': (tried_count / valid_total * 100) if valid_total > 0 else 0,
                'fully_explored': len(untried) == 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get exploration status: {e}")
            return {'error': str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get exploration intelligence statistics"""
        return {
            'exploration_decisions': self.exploration_decisions,
            'untried_actions_found': self.untried_actions_found,
            'random_selections': self.random_selections,
            'valid_combinations': self.brain.get_max_action_combinations(),
            'disjoint_pairs': self.brain.action_discretizer.get_disjoint_pairs()
        }


class SmartExplorationIntelligence(ExplorationIntelligence):
    """
    Enhanced exploration with priority-based selection
    
    Instead of random selection, prioritizes:
    1. Actions leading to unexplored states
    2. Actions with potential for new knowledge
    3. Actions that expand coverage
    """
    
    def __init__(self, 
                 brain: BrainArchitecture,
                 knowledge: KnowledgeManager):
        super().__init__(brain, knowledge)
        
        # Track exploration history
        self.exploration_history: List[Dict[str, str]] = []
        self.max_history = 1000
        
        logger.info("[INTELLIGENCE:SMART_EXPLORE] Initialized with priority selection")
    
    def decide_action(self, 
                     feedbacks: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Decide action with smart priority-based selection
        """
        self.exploration_decisions += 1
        
        try:
            untried = self.brain.get_untried_actions(feedbacks)
            
            if not untried:
                logger.debug("[SMART_EXPLORE] All valid actions tried")
                return None
            
            self.untried_actions_found += 1
            
            # Priority-based selection
            selected = self._select_with_priority(untried, feedbacks)
            
            # Track history
            self.exploration_history.append(selected)
            if len(self.exploration_history) > self.max_history:
                self.exploration_history.pop(0)
            
            action_continuous = self._labels_to_continuous(selected)
            
            logger.debug(f"[SMART_EXPLORE] Selected: {selected}")
            
            return action_continuous
            
        except Exception as e:
            logger.error(f"Smart exploration failed: {e}")
            return None
    
    def _select_with_priority(self,
                              untried: List[Dict[str, str]],
                              feedbacks: Dict[str, float]) -> Dict[str, str]:
        """
        Select action with priority scoring
        
        Priorities:
        1. Least recently tried action types
        2. Actions that change state significantly
        3. Random tiebreaker
        """
        if not untried:
            return {}
        
        # Score each untried action
        scored = []
        for action in untried:
            score = self._score_action(action)
            scored.append((score, action))
        
        # Sort by score (highest first)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return highest scored (with some randomness in top tier)
        top_tier = [a for s, a in scored[:max(1, len(scored)//3)]]
        return random.choice(top_tier)
    
    def _score_action(self, action: Dict[str, str]) -> float:
        """
        Score action for exploration priority
        """
        score = 0.0
        
        # Prefer actions not recently tried
        action_tuple = tuple(sorted(action.items()))
        recent_count = sum(
            1 for h in self.exploration_history[-100:] 
            if tuple(sorted(h.items())) == action_tuple
        )
        score -= recent_count * 10
        
        # Prefer non-NONE actions (more interesting)
        active_count = sum(1 for v in action.values() if v != 'NONE')
        score += active_count * 5
        
        # Add randomness
        score += random.random() * 2
        
        return score