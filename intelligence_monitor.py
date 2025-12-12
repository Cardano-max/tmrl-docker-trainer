"""
INTELLIGENCE: Range Monitoring

Third intelligence module - monitors if actual values are outside expected ranges
This is NOT validation, it's ongoing monitoring

EXAMPLE:
- Expected: distance between robots > 0.5m
- Actual: robots at 0.3m
- Intelligence alerts: "Robots getting under expected range"

This intelligence continuously monitors and alerts administrators
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RangeViolation:
    """Record of a range violation"""
    feedback_name: str
    expected_min: float
    expected_max: float
    actual_value: float
    timestamp: float
    frame: int
    severity: str  # 'minor', 'moderate', 'severe'
    
    def __str__(self):
        return (
            f"⚠️ {self.feedback_name}: "
            f"expected [{self.expected_min}, {self.expected_max}], "
            f"got {self.actual_value} @ frame {self.frame}"
        )


class RangeMonitorIntelligence:
    """
    Intelligence that monitors feedback ranges
    
    INTELLIGENCE DECISION:
    - Compare actual feedback values with expected ranges
    - Alert when values outside expected ranges
    - Track violation patterns
    - Suggest range adjustments
    
    This is INTELLIGENCE, not validation:
    - Validation happens at config loading (brain capacity)
    - Monitoring happens during operation (intelligence)
    """
    
    def __init__(self, feedbacks_config: Dict[str, Any]):
        """
        Initialize range monitor
        
        Args:
            feedbacks_config: Feedbacks section from config
        """
        self.config = feedbacks_config
        
        # Extract expected ranges
        self.expected_ranges = {}
        for name, config in feedbacks_config.items():
            self.expected_ranges[name] = {
                'min': config['expected_range'][0],
                'max': config['expected_range'][1],
                'unit': config['unit']
            }
        
        # Violation tracking
        self.violations: List[RangeViolation] = []
        self.violation_counts = defaultdict(int)
        self.last_violation_time = {}
        
        # Alert thresholds
        self.alert_threshold = 10  # Alert after N violations
        self.severe_threshold_multiplier = 2.0  # 2x outside range = severe
        
        # Statistics
        self.checks_performed = 0
        self.alerts_generated = 0
        
        logger.info("[INTELLIGENCE:MONITOR] Range Monitor initialized")
    
    def check_ranges(self, 
                     feedbacks: Dict[str, float],
                     frame: int) -> List[RangeViolation]:
        """
        CORE INTELLIGENCE DECISION: Check if values are in expected ranges
        
        Args:
            feedbacks: Current feedback values
            frame: Current frame number
        
        Returns:
            List of violations found
        """
        self.checks_performed += 1
        violations = []
        
        for name, value in feedbacks.items():
            if name not in self.expected_ranges:
                continue
            
            expected = self.expected_ranges[name]
            expected_min = expected['min']
            expected_max = expected['max']
            
            # Check if outside range
            if value < expected_min or value > expected_max:
                # Calculate severity
                range_size = expected_max - expected_min
                
                if value < expected_min:
                    deviation = expected_min - value
                else:
                    deviation = value - expected_max
                
                # Determine severity
                if deviation > range_size * self.severe_threshold_multiplier:
                    severity = 'severe'
                elif deviation > range_size:
                    severity = 'moderate'
                else:
                    severity = 'minor'
                
                # Create violation record
                violation = RangeViolation(
                    feedback_name=name,
                    expected_min=expected_min,
                    expected_max=expected_max,
                    actual_value=value,
                    timestamp=time.time(),
                    frame=frame,
                    severity=severity
                )
                
                violations.append(violation)
                self.violations.append(violation)
                self.violation_counts[name] += 1
                self.last_violation_time[name] = time.time()
                
                # Log based on severity
                if severity == 'severe':
                    logger.error(f"[MONITOR] SEVERE: {violation}")
                elif severity == 'moderate':
                    logger.warning(f"[MONITOR] MODERATE: {violation}")
                else:
                    logger.info(f"[MONITOR] MINOR: {violation}")
        
        # Generate alerts if threshold exceeded
        if violations:
            self._check_alert_thresholds()
        
        return violations
    
    def _check_alert_thresholds(self):
        """Check if any feedback has exceeded alert threshold"""
        for name, count in self.violation_counts.items():
            if count >= self.alert_threshold and count % self.alert_threshold == 0:
                self.alerts_generated += 1
                logger.error(
                    f"[MONITOR] 🚨 ALERT: '{name}' has {count} violations! "
                    f"Consider adjusting expected range or system constraints."
                )
    
    def get_violation_summary(self, 
                             feedback_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get summary of violations
        
        Args:
            feedback_name: Specific feedback to summarize (None = all)
        
        Returns:
            Violation summary
        """
        if feedback_name:
            violations = [v for v in self.violations if v.feedback_name == feedback_name]
        else:
            violations = self.violations
        
        if not violations:
            return {
                'total_violations': 0,
                'feedbacks_affected': [],
                'severity_breakdown': {}
            }
        
        # Calculate statistics
        severity_counts = defaultdict(int)
        for v in violations:
            severity_counts[v.severity] += 1
        
        feedbacks_affected = list(set(v.feedback_name for v in violations))
        
        return {
            'total_violations': len(violations),
            'feedbacks_affected': feedbacks_affected,
            'severity_breakdown': dict(severity_counts),
            'most_violated': max(self.violation_counts.items(), key=lambda x: x[1])[0] if self.violation_counts else None,
            'recent_violations': [str(v) for v in violations[-5:]]
        }
    
    def suggest_range_adjustment(self, 
                                 feedback_name: str) -> Optional[Dict[str, float]]:
        """
        Suggest new range based on observed violations
        
        Args:
            feedback_name: Feedback to analyze
        
        Returns:
            Suggested range or None
        """
        feedback_violations = [v for v in self.violations if v.feedback_name == feedback_name]
        
        if not feedback_violations:
            return None
        
        # Calculate observed range from violations
        actual_values = [v.actual_value for v in feedback_violations]
        observed_min = min(actual_values)
        observed_max = max(actual_values)
        
        # Add 10% buffer
        range_buffer = (observed_max - observed_min) * 0.1
        
        suggested = {
            'min': observed_min - range_buffer,
            'max': observed_max + range_buffer,
            'reason': f'Based on {len(feedback_violations)} violations',
            'current_min': self.expected_ranges[feedback_name]['min'],
            'current_max': self.expected_ranges[feedback_name]['max']
        }
        
        logger.info(
            f"[MONITOR] Suggestion for '{feedback_name}': "
            f"Change range from [{suggested['current_min']}, {suggested['current_max']}] "
            f"to [{suggested['min']:.2f}, {suggested['max']:.2f}]"
        )
        
        return suggested
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        return {
            'checks_performed': self.checks_performed,
            'total_violations': len(self.violations),
            'alerts_generated': self.alerts_generated,
            'feedbacks_monitored': len(self.expected_ranges),
            'violation_counts': dict(self.violation_counts),
            'recent_violations': [str(v) for v in self.violations[-10:]]
        }
    
    def reset_violations(self):
        """Clear violation history"""
        self.violations.clear()
        self.violation_counts.clear()
        self.last_violation_time.clear()
        logger.info("[INTELLIGENCE:MONITOR] Violations reset")