from __future__ import annotations

from collections.abc import Callable

from services.visual_model.errors import (
    VisualModelRuntimeError,
)
from services.visual_model.providers.private_runtime import (
    PrivateVisualBackend,
    PrivateVisualRuntime,
)
from services.visual_model.providers.runtime_config import (
    PRIVATE_VISUAL_RUNTIME_TYPE,
    PrivateVisualRuntimeConfiguration,
    validate_private_visual_runtime_configuration,
)
from services.visual_model.runtime import (
    VisualModelRuntime,
)


PrivateVisualBackendFactory = Callable[
    [],
    PrivateVisualBackend,
]


def build_visual_model_runtime(
    *,
    configuration: PrivateVisualRuntimeConfiguration,
    backend_factory: PrivateVisualBackendFactory,
) -> VisualModelRuntime:
    try:
        validate_private_visual_runtime_configuration(
            configuration
        )
    except ValueError as error:
        raise VisualModelRuntimeError(
            str(error)
        ) from error

    if (
        configuration.runtime_type
        != PRIVATE_VISUAL_RUNTIME_TYPE
    ):
        raise VisualModelRuntimeError(
            "The configured visual runtime type "
            "is not supported."
        )

    if not callable(backend_factory):
        raise VisualModelRuntimeError(
            "The private visual backend factory "
            "must be callable."
        )

    try:
        backend = backend_factory()
    except Exception as error:
        raise VisualModelRuntimeError(
            "The private visual backend "
            "could not be created."
        ) from error

    try:
        return PrivateVisualRuntime(
            configuration=configuration,
            backend=backend,
        )
    except VisualModelRuntimeError:
        raise
    except (
        TypeError,
        ValueError,
    ) as error:
        raise VisualModelRuntimeError(
            "The private visual runtime "
            "could not be constructed."
        ) from error
