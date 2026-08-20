class VisualProviderError(Exception):
    """Base error for visual provider operations."""


class VisualProviderConfigurationError(
    VisualProviderError,
    ValueError,
):
    """Raised when provider configuration is invalid."""


class VisualProviderRegistrationError(
    VisualProviderError,
    ValueError,
):
    """Raised when provider registration is invalid."""


class VisualProviderUnavailableError(
    VisualProviderError,
):
    """Raised when no compatible provider is available."""


class VisualProviderRequestError(
    VisualProviderError,
):
    """Raised when a provider request cannot be completed."""


class VisualProviderResponseError(
    VisualProviderError,
):
    """Raised when a provider response is invalid."""
