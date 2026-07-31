from __future__ import annotations


class VisualModelServiceError(Exception):
    """Base error for the private visual model service."""


class VisualModelRequestValidationError(
    VisualModelServiceError,
    ValueError,
):
    """Raised when a visual model request is invalid."""


class VisualModelResponseValidationError(
    VisualModelServiceError,
    ValueError,
):
    """Raised when a visual model response is invalid."""


class VisualModelRuntimeError(
    VisualModelServiceError
):
    """Raised when the configured visual runtime fails."""
