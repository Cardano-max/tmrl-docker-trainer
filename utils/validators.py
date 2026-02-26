"""
Input Validators
Ensures all inputs are valid before processing

Updated: Added numpy type support for TMRL compatibility
Updated: TMNF support -- bins optional (discovered at runtime), frame duration discovered from environment
"""

import logging
from typing import Dict, Any, List
from .exceptions import ValidationError

# Try to import numpy for type checking
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


def is_numeric(value) -> bool:
    """
    Check if value is numeric (int, float, or numpy numeric types)

    This handles:
    - Python int, float
    - numpy.int32, numpy.int64
    - numpy.float32, numpy.float64
    """
    if isinstance(value, (int, float)):
        return True

    if HAS_NUMPY:
        if isinstance(value, (np.integer, np.floating)):
            return True

    return False


class ConfigValidator:
    """Validates system configuration"""

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """
        Validate complete configuration structure.

        Required top-level keys: system_name, actions, feedbacks, environment.
        'system_config' is optional (TM2020/FalkorDB concern -- Phase 3).

        Raises:
            ValidationError: If config is invalid
        """
        required_top_level = ['system_name', 'actions', 'feedbacks', 'environment']

        for key in required_top_level:
            if key not in config:
                raise ValidationError(f"Missing required config key: {key}")

        ConfigValidator._validate_actions(config['actions'])
        ConfigValidator._validate_feedbacks(config['feedbacks'])
        ConfigValidator._validate_environment(config['environment'])

        # system_config is optional -- only validate if present (TM2020 / FalkorDB configs)
        if 'system_config' in config:
            ConfigValidator._validate_system_config(config['system_config'])

        logger.info("Configuration validated")
        return True

    @staticmethod
    def validate_tmnf_config(config: Dict[str, Any]) -> bool:
        """
        Validate a TMNF-specific configuration.

        Calls base validate_config() first, then adds TMNF-specific checks:
        - Action types must be 'binary' or 'analog'
        - environment.port must be in valid range (1-65535)

        Raises:
            ValidationError: If config is invalid
        """
        ConfigValidator.validate_config(config)

        # TMNF-specific: action types
        valid_tmnf_types = {'binary', 'analog', 'continuous'}
        for action_name, action_config in config['actions'].items():
            action_type = action_config.get('type', '')
            if action_type not in valid_tmnf_types:
                raise ValidationError(
                    f"Action '{action_name}' type '{action_type}' not valid for TMNF "
                    f"(expected: binary, analog, or continuous)"
                )

        # TMNF-specific: port range
        env = config.get('environment', {})
        if 'port' in env:
            port = env['port']
            if not isinstance(port, int) or not (1 <= port <= 65535):
                raise ValidationError(
                    f"environment.port must be an integer in range 1-65535, got: {port}"
                )

        logger.info("TMNF configuration validated")
        return True

    @staticmethod
    def _validate_actions(actions: Dict[str, Any]):
        """
        Validate actions configuration.

        - Each action requires 'type' (string) and 'range' (list of 2 numbers).
        - 'bins' is OPTIONAL. Bins are discovered at runtime (Sutton REQ-20).
        - If 'bins' is present, validate each bin has min, max, label.
        """
        if not actions:
            raise ValidationError("No actions defined")

        for action_name, action_config in actions.items():
            if 'type' not in action_config:
                raise ValidationError(f"Action '{action_name}' missing 'type'")

            if 'range' not in action_config:
                raise ValidationError(f"Action '{action_name}' missing 'range'")

            action_range = action_config['range']
            if not isinstance(action_range, list) or len(action_range) != 2:
                raise ValidationError(
                    f"Action '{action_name}' 'range' must be a list of 2 numbers"
                )
            if not is_numeric(action_range[0]) or not is_numeric(action_range[1]):
                raise ValidationError(
                    f"Action '{action_name}' 'range' values must be numeric"
                )

            # bins are optional -- only validate if present
            if 'bins' in action_config:
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
    def _validate_environment(environment: Dict[str, Any]):
        """
        Validate environment configuration.

        Checks environment has required connection info.
        Frame duration is NOT validated here — it is DISCOVERED from the
        environment at runtime (Sutton: "who defines the time stamp is
        the environment", "determined by the system not hard-coded").
        """
        # environment section must exist (checked by validate_config),
        # but its contents are flexible — host/port/type are optional
        # since different adapters have different needs.
        pass

    @staticmethod
    def _validate_system_config(system_config: Dict[str, Any]):
        """Validate system configuration (TM2020/FalkorDB -- optional section)"""
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
            if not is_numeric(value):
                raise ValidationError(
                    f"Feedback '{key}' must be numeric, got {type(value)}"
                )

            # Convert to Python float for range check
            float_val = float(value)
            if not (-1e10 < float_val < 1e10):  # Sanity check
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
            if not is_numeric(value):
                raise ValidationError(
                    f"Action '{key}' must be numeric, got {type(value)}"
                )

        return True

    @staticmethod
    def validate_frame_number(frame: int) -> bool:
        """Validate frame number"""
        # Allow numpy integers as well
        if not is_numeric(frame):
            raise ValidationError(f"Frame must be int, got {type(frame)}")

        if int(frame) < 0:
            raise ValidationError(f"Frame cannot be negative: {frame}")

        return True
