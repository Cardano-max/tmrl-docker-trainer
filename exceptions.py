"""
Custom Exceptions for Knowledge Graph System
Enables precise error handling and debugging
"""


class SystemException(Exception):
    """Base exception for all system errors"""
    pass


class ConfigurationError(SystemException):
    """Raised when configuration is invalid"""
    pass


class BrainCapacityError(SystemException):
    """Raised when brain architecture fails"""
    pass


class KnowledgeError(SystemException):
    """Raised when knowledge operations fail"""
    pass


class IntelligenceError(SystemException):
    """Raised when intelligence decision fails"""
    pass


class DiscretizationError(SystemException):
    """Raised when discretization fails"""
    pass


class GraphOperationError(SystemException):
    """Raised when graph database operations fail"""
    pass


class ValidationError(SystemException):
    """Raised when input validation fails"""
    pass


class StateNotFoundError(KnowledgeError):
    """Raised when queried state doesn't exist in knowledge"""
    pass


class ActionNotFoundError(KnowledgeError):
    """Raised when action cannot be found"""
    pass


class DatabaseConnectionError(GraphOperationError):
    """Raised when database connection fails"""
    pass


class IntervalCalculationError(DiscretizationError):
    """Raised when interval calculation fails"""
    pass