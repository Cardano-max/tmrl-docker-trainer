"""
Input Validators
Ensures all inputs are valid before processing
"""

import logging
from typing import Dict, Any, List
from exceptions import ValidationError

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates system configuration"""
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """
        Validate complete configuration structure
        
        Raises:
            ValidationError: If config is invalid
        """
        required_top_level = ['system_name', 'actions', 'feedbacks', 'system_config']
        
        for key in required_top_level:
            if key not in config:
                raise ValidationError(f"Missing required config key: {key}")
        
        ConfigValidator._validate_actions(config['actions'])
        ConfigValidator._validate_feedbacks(config['feedbacks'])
        ConfigValidator._validate_system_config(config['system_config'])
        
        logger.info("✓ Configuration validated")
        return True
    
    @staticmethod
    def _validate_actions(actions: Dict[str, Any]):
        """Validate actions configuration"""
        if not actions:
            raise ValidationError("No actions defined")
        
        for action_name, action_config in actions.items():
            if 'type' not in action_config:
                raise ValidationError(f"Action '{action_name}' missing 'type'")
            
            if action_config['type'] == 'continuous':
                if 'range' not in action_config:
                    raise ValidationError(f"Action '{action_name}' missing 'range'")
                
                if 'bins' not in action_config:
                    raise ValidationError(f"Action '{action_name}' missing 'bins'")
                
                # Validate bins
                bins = action_config['bins']
                if not bins:
                    raise ValidationError(f"Action '{action_name}' has no bins")
                
                for i, bin_info in enumerate(bins):
                    required_bin_keys = ['min', 'max', 'label']
                    for key in required_bin_keys:
                        if key not in bin_info:
                            raise ValidationError(
                                f"Action '{action_name}' bin {i} missing '{key}'"
                            )
                    
                    if bin_info['min'] >= bin_info['max']:
                        raise ValidationError(
                            f"Action '{action_name}' bin {i}: min >= max"
                        )
    
    @staticmethod
    def _validate_feedbacks(feedbacks: Dict[str, Any]):
        """Validate feedbacks configuration"""
        if not feedbacks:
            raise ValidationError("No feedbacks defined")
        
        for feedback_name, feedback_config in feedbacks.items():
            required_keys = ['description', 'unit', 'interval_size', 'expected_range']
            for key in required_keys:
                if key not in feedback_config:
                    raise ValidationError(
                        f"Feedback '{feedback_name}' missing '{key}'"
                    )
            
            if feedback_config['interval_size'] <= 0:
                raise ValidationError(
                    f"Feedback '{feedback_name}': interval_size must be > 0"
                )
            
            expected_range = feedback_config['expected_range']
            if len(expected_range) != 2:
                raise ValidationError(
                    f"Feedback '{feedback_name}': expected_range must have 2 values"
                )
            
            if expected_range[0] >= expected_range[1]:
                raise ValidationError(
                    f"Feedback '{feedback_name}': invalid range"
                )
    
    @staticmethod
    def _validate_system_config(system_config: Dict[str, Any]):
        """Validate system configuration"""
        required_keys = [
            'database_host', 'database_port', 
            'checkpoint_path', 'processing_batch_size'
        ]
        
        for key in required_keys:
            if key not in system_config:
                raise ValidationError(f"System config missing '{key}'")


class InputValidator:
    """Validates runtime inputs"""
    
    @staticmethod
    def validate_feedbacks(feedbacks: Dict[str, float], 
                          expected_keys: List[str]) -> bool:
        """
        Validate feedback dictionary
        
        Args:
            feedbacks: Feedback values
            expected_keys: Expected feedback names
        
        Raises:
            ValidationError: If invalid
        """
        if not feedbacks:
            raise ValidationError("Empty feedbacks dictionary")
        
        for key in expected_keys:
            if key not in feedbacks:
                raise ValidationError(f"Missing feedback: {key}")
            
            value = feedbacks[key]
            if not isinstance(value, (int, float)):
                raise ValidationError(
                    f"Feedback '{key}' must be numeric, got {type(value)}"
                )
            
            if not (-1e10 < value < 1e10):  # Sanity check
                raise ValidationError(
                    f"Feedback '{key}' value out of range: {value}"
                )
        
        return True
    
    @staticmethod
    def validate_action(action: Dict[str, float], 
                       expected_keys: List[str]) -> bool:
        """
        Validate action dictionary
        
        Args:
            action: Action values
            expected_keys: Expected action names
        
        Raises:
            ValidationError: If invalid
        """
        if not action:
            raise ValidationError("Empty action dictionary")
        
        for key in expected_keys:
            if key not in action:
                raise ValidationError(f"Missing action: {key}")
            
            value = action[key]
            if not isinstance(value, (int, float)):
                raise ValidationError(
                    f"Action '{key}' must be numeric, got {type(value)}"
                )
        
        return True
    
    @staticmethod
    def validate_frame_number(frame: int) -> bool:
        """Validate frame number"""
        if not isinstance(frame, int):
            raise ValidationError(f"Frame must be int, got {type(frame)}")
        
        if frame < 0:
            raise ValidationError(f"Frame cannot be negative: {frame}")
        
        return True