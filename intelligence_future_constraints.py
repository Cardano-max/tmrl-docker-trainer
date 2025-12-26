"""
INTELLIGENCE: Future Constraints

Validates future states against constraints before taking actions

SUPERVISOR'S FRAMEWORK:
"Hard Constraints: MUST obey (e.g., don't crash)"
"Soft Constraints: SHOULD follow (e.g., prefer right side)"

KEY FEATURES:
1. Hard vs Soft constraint types
2. Simulation mode (allow violations for learning)
3. Real-world mode (enforce hard constraints)
4. Constraint factory for easy creation
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from state_manager import StateVector
from exceptions import IntelligenceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConstraintType(Enum):
    """Type of constraint"""
    HARD = "hard"    # MUST obey - system stops if violated
    SOFT = "soft"    # SHOULD follow - warning only


@dataclass
class Constraint:
    """
    Single constraint definition
    
    SUPERVISOR'S EXAMPLE:
    "Don't leave the track" = Hard constraint
    "Stay on right side" = Soft constraint
    """
    name: str
    description: str
    constraint_type: ConstraintType
    check_function: Callable[[StateVector, Dict[str, str]], Tuple[bool, str]]
    graph_name: Optional[str] = None  # Which graph this applies to (None = all)
    enabled: bool = True
    violations: int = field(default=0)
    last_violation: Optional[float] = field(default=None)
    
    def check(self, 
              predicted_state: StateVector, 
              action: Dict[str, str]) -> Tuple[bool, str]:
        """
        Check if constraint is satisfied
        
        Args:
            predicted_state: Future state to validate
            action: Action being considered
        
        Returns:
            (satisfied, message) tuple
        """
        if not self.enabled:
            return True, "Constraint disabled"
        
        try:
            satisfied, message = self.check_function(predicted_state, action)
            
            if not satisfied:
                self.violations += 1
                self.last_violation = time.time()
            
            return satisfied, message
            
        except Exception as e:
            logger.error(f"Constraint check failed for {self.name}: {e}")
            return True, f"Check failed: {e}"  # Fail open


class ConstraintFactory:
    """
    Factory for creating common constraint types
    
    Makes it easy to define constraints without writing check functions
    """
    
    @staticmethod
    def create_range_constraint(graph_name: str,
                                min_val: float,
                                max_val: float,
                                constraint_type: ConstraintType = ConstraintType.SOFT,
                                description: str = "") -> Tuple[str, str, ConstraintType, Callable]:
        """
        Create range constraint for a feedback
        
        Args:
            graph_name: Which feedback to constrain
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            constraint_type: HARD or SOFT
            description: Human-readable description
        
        Returns:
            Tuple for Constraint initialization
        """
        name = f"{graph_name}_range_{min_val}_{max_val}"
        
        if not description:
            description = f"{graph_name} must be in range [{min_val}, {max_val}]"
        
        def check_range(state: StateVector, action: Dict[str, str]) -> Tuple[bool, str]:
            if graph_name not in state.graph_positions:
                return True, f"Graph {graph_name} not in state"
            
            value = state.graph_positions[graph_name]
            
            if value < min_val:
                return False, f"{graph_name}={value:.2f} < min {min_val}"
            if value > max_val:
                return False, f"{graph_name}={value:.2f} > max {max_val}"
            
            return True, "In range"
        
        return (name, description, constraint_type, check_range)
    
    @staticmethod
    def create_threshold_constraint(graph_name: str,
                                   threshold: float,
                                   comparison: str = ">",
                                   constraint_type: ConstraintType = ConstraintType.SOFT,
                                   description: str = "") -> Tuple[str, str, ConstraintType, Callable]:
        """
        Create threshold constraint (greater than / less than)
        
        Args:
            graph_name: Which feedback to constrain
            threshold: Threshold value
            comparison: ">" or "<"
            constraint_type: HARD or SOFT
            description: Human-readable description
        """
        name = f"{graph_name}_{comparison}_{threshold}"
        
        if not description:
            description = f"{graph_name} must be {comparison} {threshold}"
        
        def check_threshold(state: StateVector, action: Dict[str, str]) -> Tuple[bool, str]:
            if graph_name not in state.graph_positions:
                return True, f"Graph {graph_name} not in state"
            
            value = state.graph_positions[graph_name]
            
            if comparison == ">":
                satisfied = value > threshold
            elif comparison == ">=":
                satisfied = value >= threshold
            elif comparison == "<":
                satisfied = value < threshold
            elif comparison == "<=":
                satisfied = value <= threshold
            else:
                return True, f"Unknown comparison: {comparison}"
            
            if satisfied:
                return True, f"{graph_name}={value:.2f} {comparison} {threshold}"
            else:
                return False, f"{graph_name}={value:.2f} NOT {comparison} {threshold}"
        
        return (name, description, constraint_type, check_threshold)
    
    @staticmethod
    def create_action_constraint(forbidden_action: Dict[str, str],
                                constraint_type: ConstraintType = ConstraintType.HARD,
                                description: str = "") -> Tuple[str, str, ConstraintType, Callable]:
        """
        Create constraint that forbids specific action
        
        Args:
            forbidden_action: Action labels that are forbidden
            constraint_type: HARD or SOFT
            description: Human-readable description
        """
        name = f"no_action_{'_'.join(f'{k}_{v}' for k, v in sorted(forbidden_action.items()))}"
        
        if not description:
            description = f"Action {forbidden_action} is forbidden"
        
        def check_action(state: StateVector, action: Dict[str, str]) -> Tuple[bool, str]:
            matches = all(
                action.get(k) == v 
                for k, v in forbidden_action.items()
            )
            
            if matches:
                return False, f"Forbidden action: {forbidden_action}"
            return True, "Action allowed"
        
        return (name, description, constraint_type, check_action)


class FutureConstraintsIntelligence:
    """
    Intelligence for validating future states against constraints
    
    SUPERVISOR'S FRAMEWORK:
    "Before acting, predict and validate"
    "Hard constraints MUST be obeyed"
    "Soft constraints SHOULD be followed"
    
    MODES:
    - Simulation: Allow violations (for learning)
    - Real-world: Enforce hard constraints (for safety)
    """
    
    def __init__(self, simulation_mode: bool = True):
        """
        Initialize future constraints intelligence
        
        Args:
            simulation_mode: If True, violations are warnings only
                           If False, hard violations prevent action
        """
        self.simulation_mode = simulation_mode
        self.constraints: Dict[str, Constraint] = {}
        
        # Statistics
        self.validations_performed = 0
        self.hard_violations = 0
        self.soft_violations = 0
        self.actions_blocked = 0
        
        # History
        self.violation_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        logger.info(
            f"[INTELLIGENCE:FUTURE_CONSTRAINTS] Initialized "
            f"(simulation_mode={simulation_mode})"
        )
    
    def add_constraint(self,
                      name: str,
                      description: str,
                      constraint_type: ConstraintType,
                      check_function: Callable) -> bool:
        """
        Add constraint to validation
        
        Args:
            name: Unique constraint name
            description: Human-readable description
            constraint_type: HARD or SOFT
            check_function: Function(state, action) -> (bool, str)
        
        Returns:
            True if added successfully
        """
        if name in self.constraints:
            logger.warning(f"Constraint {name} already exists, updating")
        
        constraint = Constraint(
            name=name,
            description=description,
            constraint_type=constraint_type,
            check_function=check_function
        )
        
        self.constraints[name] = constraint
        
        type_str = "hard" if constraint_type == ConstraintType.HARD else "soft"
        logger.info(f"[CONSTRAINTS] Added {type_str} constraint: '{name}' - {description}")
        
        return True
    
    def remove_constraint(self, name: str) -> bool:
        """Remove constraint by name"""
        if name in self.constraints:
            del self.constraints[name]
            logger.info(f"[CONSTRAINTS] Removed: {name}")
            return True
        return False
    
    def enable_constraint(self, name: str, enabled: bool = True) -> bool:
        """Enable/disable constraint"""
        if name in self.constraints:
            self.constraints[name].enabled = enabled
            status = "enabled" if enabled else "disabled"
            logger.info(f"[CONSTRAINTS] {name} {status}")
            return True
        return False
    
    def validate_future_state(self,
                             predicted_state: StateVector,
                             action: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate predicted future state against all constraints
        
        SUPERVISOR'S PROCESS:
        1. Check each constraint
        2. Hard violations block action (unless simulation mode)
        3. Soft violations are warnings
        
        Args:
            predicted_state: What we predict will happen
            action: Action we're about to take
        
        Returns:
            (allowed, violations) tuple
        """
        self.validations_performed += 1
        
        violations = []
        has_hard_violation = False
        
        for name, constraint in self.constraints.items():
            satisfied, message = constraint.check(predicted_state, action)
            
            if not satisfied:
                violation_str = f"{name}: {message}"
                violations.append(violation_str)
                
                if constraint.constraint_type == ConstraintType.HARD:
                    has_hard_violation = True
                    self.hard_violations += 1
                    logger.warning(f"[CONSTRAINTS] HARD VIOLATION: {violation_str}")
                else:
                    self.soft_violations += 1
                    logger.info(f"[CONSTRAINTS] soft violation: {violation_str}")
                
                # Record in history
                self.violation_history.append({
                    'constraint': name,
                    'type': constraint.constraint_type.value,
                    'message': message,
                    'action': action,
                    'predicted_state': predicted_state.to_dict(),
                    'timestamp': time.time()
                })
                
                if len(self.violation_history) > self.max_history:
                    self.violation_history.pop(0)
        
        # Determine if action is allowed
        if has_hard_violation and not self.simulation_mode:
            self.actions_blocked += 1
            allowed = False
        else:
            allowed = True
        
        return allowed, violations
    
    def validate_action_sequence(self,
                                current_state: StateVector,
                                action_sequence: List[Dict[str, str]],
                                predict_function: Callable) -> Dict[str, Any]:
        """
        Validate sequence of actions
        
        Useful for planning ahead
        
        Args:
            current_state: Starting state
            action_sequence: Sequence of actions to validate
            predict_function: Function to predict next state
        
        Returns:
            Validation results for entire sequence
        """
        results = {
            'valid': True,
            'steps': [],
            'first_violation_at': None
        }
        
        state = current_state
        
        for i, action in enumerate(action_sequence):
            # Predict next state
            predicted = predict_function(state, action)
            
            # Validate
            allowed, violations = self.validate_future_state(predicted, action)
            
            step_result = {
                'step': i,
                'action': action,
                'predicted_state': predicted.to_dict(),
                'allowed': allowed,
                'violations': violations
            }
            
            results['steps'].append(step_result)
            
            if not allowed and results['valid']:
                results['valid'] = False
                results['first_violation_at'] = i
            
            # Update state for next iteration
            state = predicted
        
        return results
    
    def get_constraint_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all constraints"""
        summary = {}
        
        for name, constraint in self.constraints.items():
            summary[name] = {
                'description': constraint.description,
                'type': constraint.constraint_type.value,
                'enabled': constraint.enabled,
                'violations': constraint.violations,
                'last_violation': constraint.last_violation
            }
        
        return summary
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get constraint validation statistics"""
        hard_count = sum(
            1 for c in self.constraints.values() 
            if c.constraint_type == ConstraintType.HARD
        )
        soft_count = len(self.constraints) - hard_count
        
        return {
            'simulation_mode': self.simulation_mode,
            'total_constraints': len(self.constraints),
            'hard_constraints': hard_count,
            'soft_constraints': soft_count,
            'validations_performed': self.validations_performed,
            'hard_violations': self.hard_violations,
            'soft_violations': self.soft_violations,
            'actions_blocked': self.actions_blocked,
            'constraints': self.get_constraint_summary()
        }
    
    def set_simulation_mode(self, enabled: bool):
        """
        Set simulation mode
        
        Args:
            enabled: True for simulation (allow violations)
                    False for real-world (enforce hard constraints)
        """
        self.simulation_mode = enabled
        mode_str = "SIMULATION" if enabled else "REAL-WORLD"
        logger.info(f"[CONSTRAINTS] Mode set to: {mode_str}")
    
    def clear_statistics(self):
        """Clear all statistics"""
        self.validations_performed = 0
        self.hard_violations = 0
        self.soft_violations = 0
        self.actions_blocked = 0
        self.violation_history.clear()
        
        for constraint in self.constraints.values():
            constraint.violations = 0
            constraint.last_violation = None
        
        logger.info("[CONSTRAINTS] Statistics cleared")