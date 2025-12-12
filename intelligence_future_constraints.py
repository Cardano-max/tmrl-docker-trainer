"""
INTELLIGENCE: Future State Constraints V3

REQUIREMENT:
"Validation on future state for goal accomplishment"

Example:
- Goal: Stay on right side of road
- Before action: Check if future position violates goal
- If violates → Don't take that action

This is constraint-based planning intelligence
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from state_manager import StateVector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConstraintType(Enum):
    """Type of constraint"""
    HARD = "hard"  # MUST not violate (system stops/rejects action)
    SOFT = "soft"  # SHOULD not violate (warning only)


@dataclass
class Constraint:
    """
    Single constraint definition
    
    Attributes:
        name: Constraint identifier
        type: Hard or soft
        check_function: Function that validates state
        description: Human-readable description
    """
    name: str
    type: ConstraintType
    check_function: Callable[[StateVector], bool]
    description: str
    
    def validate(self, state: StateVector) -> bool:
        """
        Validate state against constraint
        
        Returns:
            True if constraint satisfied, False if violated
        """
        try:
            return self.check_function(state)
        except Exception as e:
            logger.error(f"Constraint '{self.name}' check failed: {e}")
            return False


@dataclass
class ConstraintViolation:
    """Record of constraint violation"""
    constraint_name: str
    constraint_type: ConstraintType
    state: StateVector
    action: Dict[str, str]
    timestamp: float
    
    def __repr__(self) -> str:
        type_str = "🛑 HARD" if self.constraint_type == ConstraintType.HARD else "⚠ SOFT"
        return f"{type_str} violation: {self.constraint_name} @ frame {self.state.frame}"


class FutureConstraintsIntelligence:
    """
    Future State Constraints Intelligence
    
    'CONCEPT:
    "Person in front, cliff on right, open road on left.
     Validate future states before choosing action.
     Don't go right (cliff = hard constraint violation)."
    
    PURPOSE:
    - Define goals as constraints
    - Check future state BEFORE taking action
    - Reject actions that violate hard constraints
    - Warn about soft constraint violations
    """
    
    def __init__(self, simulation_mode: bool = True):
        """
        Initialize future constraints intelligence
        
        Args:
            simulation_mode: If True, allow violations for learning
                           If False (real world), enforce hard constraints
        """
        self.simulation_mode = simulation_mode
        
        # Constraints storage
        self.constraints: Dict[str, Constraint] = {}
        
        # Violation tracking
        self.violations: List[ConstraintViolation] = []
        self.hard_violations_blocked = 0
        self.soft_violations_warned = 0
        
        logger.info(
            f"[INTELLIGENCE:FUTURE_CONSTRAINTS] Initialized "
            f"(simulation_mode={simulation_mode})"
        )
    
    def add_constraint(self,
                      name: str,
                      constraint_type: ConstraintType,
                      check_function: Callable[[StateVector], bool],
                      description: str):
        """
        Add new constraint
        
        Args:
            name: Unique constraint identifier
            constraint_type: Hard or soft
            check_function: Function(state) -> bool (True = satisfied)
            description: Human-readable description
        """
        constraint = Constraint(
            name=name,
            type=constraint_type,
            check_function=check_function,
            description=description
        )
        
        self.constraints[name] = constraint
        
        logger.info(
            f"[CONSTRAINTS] Added {constraint_type.value} constraint: "
            f"'{name}' - {description}"
        )
    
    def remove_constraint(self, name: str):
        """Remove constraint by name"""
        if name in self.constraints:
            del self.constraints[name]
            logger.info(f"[CONSTRAINTS] Removed constraint: '{name}'")
    
    def validate_future_state(self,
                             future_state: StateVector,
                             action: Dict[str, str]) -> tuple[bool, List[ConstraintViolation]]:
        """
        Validate future state against all constraints
        
        CRITICAL FUNCTION for goal-oriented behavior
        
        Args:
            future_state: Predicted/planned future state
            action: Action that would lead to this state
        
        Returns:
            (allowed, violations)
            - allowed: True if action can be taken
            - violations: List of constraint violations
        """
        import time
        
        violations = []
        hard_constraint_violated = False
        
        # Check each constraint
        for constraint in self.constraints.values():
            satisfied = constraint.validate(future_state)
            
            if not satisfied:
                # Constraint violated
                violation = ConstraintViolation(
                    constraint_name=constraint.name,
                    constraint_type=constraint.type,
                    state=future_state,
                    action=action,
                    timestamp=time.time()
                )
                
                violations.append(violation)
                self.violations.append(violation)
                
                if constraint.type == ConstraintType.HARD:
                    hard_constraint_violated = True
                    self.hard_violations_blocked += 1
                    logger.error(f"[CONSTRAINTS] {violation}")
                else:
                    self.soft_violations_warned += 1
                    logger.warning(f"[CONSTRAINTS] {violation}")
        
        # In simulation mode, allow all actions (for learning)
        # In real world mode, block hard constraint violations
        if self.simulation_mode:
            allowed = True
        else:
            allowed = not hard_constraint_violated
        
        return allowed, violations
    
    def get_violated_constraints(self,
                                state: StateVector) -> List[str]:
        """Get list of constraint names violated by state"""
        violated = []
        
        for name, constraint in self.constraints.items():
            if not constraint.validate(state):
                violated.append(name)
        
        return violated
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get constraint validation statistics"""
        return {
            'constraints_defined': len(self.constraints),
            'hard_constraints': sum(
                1 for c in self.constraints.values() 
                if c.type == ConstraintType.HARD
            ),
            'soft_constraints': sum(
                1 for c in self.constraints.values() 
                if c.type == ConstraintType.SOFT
            ),
            'total_violations': len(self.violations),
            'hard_violations_blocked': self.hard_violations_blocked,
            'soft_violations_warned': self.soft_violations_warned,
            'simulation_mode': self.simulation_mode,
            'recent_violations': [str(v) for v in self.violations[-10:]]
        }
    
    def clear_violations(self):
        """Clear violation history"""
        self.violations.clear()
        logger.info("[CONSTRAINTS] Violation history cleared")


# ============================================================================
# PREDEFINED CONSTRAINT FACTORIES
# ============================================================================

class ConstraintFactory:
    """Factory for creating common constraints"""
    
    @staticmethod
    def create_range_constraint(graph_name: str,
                                min_val: float,
                                max_val: float,
                                constraint_type: ConstraintType,
                                description: str = None) -> tuple:
        """
        Create range constraint for specific graph
        
        Returns:
            (name, constraint_type, check_function, description)
        """
        name = f"{graph_name}_range_{min_val}_{max_val}"
        
        if description is None:
            description = f"{graph_name} must be in [{min_val}, {max_val}]"
        
        def check_function(state: StateVector) -> bool:
            if graph_name not in state.graph_positions:
                return True  # Can't violate if not present
            value = state.graph_positions[graph_name]
            return min_val <= value <= max_val
        
        return (name, constraint_type, check_function, description)
    
    @staticmethod
    def create_comparison_constraint(graph_name_a: str,
                                    graph_name_b: str,
                                    operator: str,  # '<', '>', '<=', '>='
                                    constraint_type: ConstraintType,
                                    description: str = None) -> tuple:
        """
        Create comparison constraint between two graphs
        
        Example: speed < lidar_distance (don't go fast when close)
        """
        name = f"{graph_name_a}_{operator}_{graph_name_b}"
        
        if description is None:
            description = f"{graph_name_a} {operator} {graph_name_b}"
        
        def check_function(state: StateVector) -> bool:
            if (graph_name_a not in state.graph_positions or 
                graph_name_b not in state.graph_positions):
                return True
            
            val_a = state.graph_positions[graph_name_a]
            val_b = state.graph_positions[graph_name_b]
            
            if operator == '<':
                return val_a < val_b
            elif operator == '>':
                return val_a > val_b
            elif operator == '<=':
                return val_a <= val_b
            elif operator == '>=':
                return val_a >= val_b
            else:
                logger.error(f"Unknown operator: {operator}")
                return True
        
        return (name, constraint_type, check_function, description)