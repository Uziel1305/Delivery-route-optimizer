class OptimizationError(Exception):
    """Base class for all app/optimization errors."""


class InfeasibleProblemError(OptimizationError):
    """Raised when no algorithm can place every stop within courier windows."""


class AlgorithmTimeoutError(OptimizationError):
    """Raised when an algorithm exceeds its time budget without a usable result."""


class UnknownAlgorithmError(OptimizationError):
    """Raised when registry.get_algorithm() is asked for an unregistered key."""


class DuplicateAlgorithmKeyError(OptimizationError):
    """Raised at import time if two algorithms register the same key."""
