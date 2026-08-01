from __future__ import annotations

from dataclasses import dataclass

from services.visual_model.config import (
    VisualModelServiceConfiguration,
    validate_visual_model_service_configuration,
)
from services.visual_model.errors import (
    VisualModelRuntimeError,
    VisualModelServiceError,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualModelRuntime,
    VisualRuntimeHealth,
)
from services.visual_model.validation import (
    validate_visual_model_request,
    validate_visual_model_response,
)


@dataclass
class VisualModelCoordinator:
    runtime: VisualModelRuntime
    configuration: VisualModelServiceConfiguration

    def __post_init__(self) -> None:
        validate_visual_model_service_configuration(
            self.configuration
        )

        if not isinstance(
            self.runtime,
            VisualModelRuntime,
        ):
            raise TypeError(
                "runtime must implement "
                "VisualModelRuntime."
            )

    def health_check(self) -> VisualRuntimeHealth:
        if not self.configuration.enabled:
            return VisualRuntimeHealth(
                available=False,
                provider="",
                model_id="",
                message=(
                    "The visual model service "
                    "is disabled."
                ),
                details=(),
            )

        try:
            health = self.runtime.health_check()
        except VisualModelServiceError:
            raise
        except Exception as error:
            raise VisualModelRuntimeError(
                "The visual runtime health check failed."
            ) from error

        if not isinstance(
            health,
            VisualRuntimeHealth,
        ):
            raise VisualModelRuntimeError(
                "The visual runtime returned "
                "an invalid health response."
            )

        return health

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        if not self.configuration.enabled:
            raise VisualModelRuntimeError(
                "The visual model service is disabled."
            )

        validate_visual_model_request(
            request,
            maximum_image_size_bytes=(
                self.configuration
                .maximum_image_size_bytes
            ),
            allowed_media_types=frozenset(
                self.configuration
                .allowed_media_types
            ),
        )

        if (
            self.configuration
            .require_healthy_runtime
        ):
            health = self.health_check()

            if not health.available:
                message = (
                    health.message.strip()
                    or (
                        "The visual runtime "
                        "is unavailable."
                    )
                )

                raise VisualModelRuntimeError(
                    message
                )

        try:
            response = self.runtime.analyze(
                request
            )
        except VisualModelServiceError:
            raise
        except Exception as error:
            raise VisualModelRuntimeError(
                "The visual runtime failed "
                "while processing the request."
            ) from error

        if not isinstance(
            response,
            VisualModelResponse,
        ):
            raise VisualModelRuntimeError(
                "The visual runtime returned "
                "an invalid response type."
            )

        validate_visual_model_response(
            response,
            expected_request_id=(
                request.request_id
            ),
        )

        return response
