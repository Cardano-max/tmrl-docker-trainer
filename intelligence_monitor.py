"""
INTELLIGENCE: Range Monitor

Monitors feedback values and alerts when outside expected ranges

SUPERVISOR'S FRAMEWORK:
"Monitor - alert when values outside expected ranges"

KEY FEATURES:
1. Per-feedback range checking
2. Configurable alert thresholds
3. History tracking
4. Environment-agnostic
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

from exceptions import IntelligenceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RangeAlert:
    """Alert when value goes outside expected range"""
    feedback_name: str
    value: float
    expected_min: float
    expected_max: float
    deviation: float
    severity: str  # 'warning', 'critical'
    timestamp: float
    
    def __repr__(self) -> str:
        return (f"RangeAlert({self.feedback_name}={self.value:.2f}, "
                f"expected=[{self.expected_min:.2f}, {self.expected_max:.2f}], "
                f"severity={self.severity})")


class RangeMonitorIntelligence:
    """
    Monitors feedback values for range violations
    
    SUPERVISOR'S CONCEPT:
    "Monitor - system should know when things are outside normal"
    
    This is INTELLIGENCE - using knowledge about expected ranges
    to detect anomalies.
    """
    
    # Severity levels
    SEVERITY_WARNING = 'warning'
    SEVERITY_CRITICAL = 'critical'
    
    def __init__(self, 
                 feedbacks_config: Dict[str, Any],
                 alert_threshold: int = 10):
        """
        Initialize range monitor
        
        Args:
            feedbacks_config: Feedback configuration from system config
            alert_threshold: Number of alerts before escalation
        """
        self.feedbacks_config = feedbacks_config
        self.alert_threshold = alert_threshold
        
        # Extract expected ranges
        self.expected_ranges: Dict[str, tuple] = {}
        for name, config in feedbacks_config.items():
            self.expected_ranges[name] = (
                config['expected_range'][0],
                config['expected_range'][1]
            )
        
        # Alert tracking
        self.alerts: List[RangeAlert] = []
        self.max_alerts = 1000
        
        # Per-feedback statistics
        self.violation_counts: Dict[str, int] = defaultdict(int)
        self.checks_performed = 0
        
        logger.info("[INTELLIGENCE:MONITOR] Range Monitor initialized")
    
    def check_feedbacks(self, 
                       feedbacks: Dict[str, float]) -> List[RangeAlert]:
        """
        Check all feedbacks for range violations
        
        Args:
            feedbacks: Current feedback values
        
        Returns:
            List of alerts for any violations
        """
        self.checks_performed += 1
        new_alerts = []
        
        for name, value in feedbacks.items():
            if name not in self.expected_ranges:
                continue
            
            expected_min, expected_max = self.expected_ranges[name]
            
            if value < expected_min or value > expected_max:
                # Calculate deviation
                if value < expected_min:
                    deviation = expected_min - value
                else:
                    deviation = value - expected_max
                
                # Determine severity
                range_size = expected_max - expected_min
                deviation_percent = (deviation / range_size) * 100 if range_size > 0 else 100
                
                severity = (
                    self.SEVERITY_CRITICAL if deviation_percent > 50 
                    else self.SEVERITY_WARNING
                )
                
                alert = RangeAlert(
                    feedback_name=name,
                    value=value,
                    expected_min=expected_min,
                    expected_max=expected_max,
                    deviation=deviation,
                    severity=severity,
                    timestamp=time.time()
                )
                
                new_alerts.append(alert)
                self.violation_counts[name] += 1
                
                # Log alert
                log_level = logging.WARNING if severity == self.SEVERITY_WARNING else logging.ERROR
                logger.log(log_level, f"[MONITOR] {alert}")
        
        # Store alerts
        self.alerts.extend(new_alerts)
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        
        return new_alerts
    
    def check_single(self, 
                    feedback_name: str, 
                    value: float) -> Optional[RangeAlert]:
        """
        Check single feedback value
        
        Args:
            feedback_name: Name of feedback
            value: Current value
        
        Returns:
            Alert if violation, None otherwise
        """
        alerts = self.check_feedbacks({feedback_name: value})
        return alerts[0] if alerts else None
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Get summary of all violations"""
        recent_alerts = self.alerts[-100:]
        
        return {
            'total_checks': self.checks_performed,
            'total_violations': sum(self.violation_counts.values()),
            'violations_by_feedback': dict(self.violation_counts),
            'recent_alerts': len(recent_alerts),
            'warning_count': sum(1 for a in recent_alerts if a.severity == self.SEVERITY_WARNING),
            'critical_count': sum(1 for a in recent_alerts if a.severity == self.SEVERITY_CRITICAL)
        }
    
    def is_value_in_range(self, 
                         feedback_name: str, 
                         value: float) -> bool:
        """
        Quick check if value is in expected range
        
        Args:
            feedback_name: Name of feedback
            value: Value to check
        
        Returns:
            True if in range
        """
        if feedback_name not in self.expected_ranges:
            return True  # Unknown feedback - assume OK
        
        expected_min, expected_max = self.expected_ranges[feedback_name]
        return expected_min <= value <= expected_max
    
    def get_expected_range(self, feedback_name: str) -> Optional[tuple]:
        """Get expected range for feedback"""
        return self.expected_ranges.get(feedback_name)
    
    def get_recent_alerts(self, 
                         count: int = 10,
                         feedback_name: Optional[str] = None) -> List[RangeAlert]:
        """
        Get recent alerts
        
        Args:
            count: Number of alerts to return
            feedback_name: Filter by specific feedback
        
        Returns:
            List of recent alerts
        """
        alerts = self.alerts
        
        if feedback_name:
            alerts = [a for a in alerts if a.feedback_name == feedback_name]
        
        return alerts[-count:]
    
    def clear_alerts(self):
        """Clear all stored alerts"""
        self.alerts.clear()
        self.violation_counts.clear()
        logger.info("[MONITOR] Alerts cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitor statistics"""
        return {
            'checks_performed': self.checks_performed,
            'total_alerts': len(self.alerts),
            'violation_counts': dict(self.violation_counts),
            'expected_ranges': self.expected_ranges,
            'alert_threshold': self.alert_threshold,
            **self.get_violation_summary()
        }


class AdaptiveRangeMonitor(RangeMonitorIntelligence):
    """
    Enhanced monitor that adapts ranges based on observations
    
    SUPERVISOR'S CONCEPT:
    "Learning - update internal model based on experience"
    
    This monitor can expand expected ranges when consistent
    out-of-range values are observed.
    """
    
    def __init__(self, 
                 feedbacks_config: Dict[str, Any],
                 alert_threshold: int = 10,
                 adaptation_rate: float = 0.01):
        super().__init__(feedbacks_config, alert_threshold)
        
        self.adaptation_rate = adaptation_rate
        
        # Track observed ranges
        self.observed_mins: Dict[str, float] = {}
        self.observed_maxs: Dict[str, float] = {}
        
        for name in feedbacks_config:
            self.observed_mins[name] = float('inf')
            self.observed_maxs[name] = float('-inf')
        
        logger.info("[MONITOR:ADAPTIVE] Adaptive Range Monitor initialized")
    
    def check_feedbacks(self, 
                       feedbacks: Dict[str, float]) -> List[RangeAlert]:
        """Check feedbacks and update observed ranges"""
        # Update observed ranges
        for name, value in feedbacks.items():
            if name in self.observed_mins:
                self.observed_mins[name] = min(self.observed_mins[name], value)
                self.observed_maxs[name] = max(self.observed_maxs[name], value)
        
        # Standard check
        return super().check_feedbacks(feedbacks)
    
    def get_observed_ranges(self) -> Dict[str, tuple]:
        """Get observed value ranges"""
        ranges = {}
        for name in self.observed_mins:
            if self.observed_mins[name] != float('inf'):
                ranges[name] = (
                    self.observed_mins[name],
                    self.observed_maxs[name]
                )
        return ranges
    
    def adapt_ranges(self):
        """
        Adapt expected ranges based on observations
        
        Expands ranges slightly if consistent out-of-range observations
        """
        for name, (expected_min, expected_max) in self.expected_ranges.items():
            observed_min = self.observed_mins.get(name, expected_min)
            observed_max = self.observed_maxs.get(name, expected_max)
            
            # Expand if observed is outside expected
            new_min = expected_min
            new_max = expected_max
            
            if observed_min < expected_min:
                # Gradually expand minimum
                new_min = expected_min - (expected_min - observed_min) * self.adaptation_rate
            
            if observed_max > expected_max:
                # Gradually expand maximum
                new_max = expected_max + (observed_max - expected_max) * self.adaptation_rate
            
            if new_min != expected_min or new_max != expected_max:
                self.expected_ranges[name] = (new_min, new_max)
                logger.info(
                    f"[ADAPTIVE] Range adapted for {name}: "
                    f"[{expected_min:.2f}, {expected_max:.2f}] -> "
                    f"[{new_min:.2f}, {new_max:.2f}]"
                )