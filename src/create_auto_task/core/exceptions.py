"""Domain exceptions used by CAT parsing, validation and execution."""


class CATError(Exception):
    """Base exception for CAT-related errors."""


class CATParseError(CATError):
    """Raised when a CAT document cannot be decoded or parsed."""


class CATValidationError(CATError):
    """Raised when a CAT document is structurally or semantically invalid."""


class CATExecutionError(CATError):
    """Raised when an action cannot be executed."""


class CATCancelled(CATError):
    """Raised when execution is cancelled between actions."""
