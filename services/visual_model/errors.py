from __future__ import annotations


class VisualModelContractError(ValueError):
    """Base error for invalid visual-model service contracts."""


class VisualModelRequestValidationError(
    VisualModelContractError
):
    """Raised when a visual-model request is invalid."""


class VisualModelResponseValidationError(
    VisualModelContractError
):
    """Raised when a visual-model response is invalid."""


class VisualModelRuntimeError(RuntimeError):
    """Base error raised by a visual-model runtime."""


class VisualModelRuntimeUnavailableError(
    VisualModelRuntimeError
):
    """Raised when the configured runtime cannot process requests."""
