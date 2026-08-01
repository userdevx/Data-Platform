from __future__ import annotations

from uuid import uuid4

import pytest

from services.visual_model.config import (
    VisualModelServiceConfiguration,
)
from services.visual_model.coordinator import (
    VisualModelCoordinator,
)
from services.visual_model.errors import (
    VisualModelRequestValidationError,
    VisualModelResponseValidationError,
    VisualModelRuntimeError,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualRuntimeHealth,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_configuration(
    *,
    enabled: bool = True,
    require_healthy_runtime: bool = True,
) -> VisualModelServiceConfiguration:
    return VisualModelServiceConfiguration(
        enabled=enabled,
        maximum_image_size_bytes=1024,
        allowed_media_types=(
            "image/png",
        ),
        require_healthy_runtime=(
            require_healthy_runtime
        ),
    )


def build_request(
    **overrides,
) -> VisualModelRequest:
    values = {
        "request_id": runtime_value(
            "request"
        ),
        "question": runtime_value(
            "question"
        ),
        "image_data": b"image-data",
        "media_type": "image/png",
        "response_schema": {
            "type": "object",
        },
        "metadata": {},
    }

    values.update(overrides)

    return VisualModelRequest(**values)


def build_response(
    request_id: str,
    **overrides,
) -> VisualModelResponse:
    values = {
        "request_id": request_id,
        "provider": runtime_value(
            "provider"
        ),
        "model_id": runtime_value(
            "model"
        ),
        "scene_description": (
            runtime_value(
                "scene-description"
            )
        ),
        "entities": (),
        "relations": (),
        "visible_text": (),
        "uncertainty": (),
        "duration_ms": 1,
        "validation_passed": True,
        "warnings": (),
        "metadata": {},
    }

    values.update(overrides)

    return VisualModelResponse(**values)


class HealthyRuntime:
    def __init__(self) -> None:
        self.health_check_count = 0
        self.analyze_count = 0

    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        self.health_check_count += 1

        return VisualRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        self.analyze_count += 1

        return build_response(
            request.request_id
        )


class UnavailableRuntime:
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        return VisualRuntimeHealth(
            available=False,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message=runtime_value(
                "unavailable"
            ),
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        raise AssertionError(
            "analyze must not be called"
        )


class FailingRuntime:
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        return VisualRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        del request

        raise RuntimeError(
            "runtime failure"
        )


class WrongRequestRuntime:
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        return VisualRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        del request

        return build_response(
            runtime_value(
                "different-request"
            )
        )


class InvalidResponseRuntime:
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        return VisualRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ):
        del request

        return {
            "invalid": True,
        }


def test_disabled_coordinator_health() -> None:
    runtime = HealthyRuntime()

    coordinator = VisualModelCoordinator(
        runtime=runtime,
        configuration=build_configuration(
            enabled=False
        ),
    )

    health = coordinator.health_check()

    assert health.available is False
    assert runtime.health_check_count == 0


def test_disabled_service_rejects_analysis() -> None:
    runtime = HealthyRuntime()

    coordinator = VisualModelCoordinator(
        runtime=runtime,
        configuration=build_configuration(
            enabled=False
        ),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="disabled",
    ):
        coordinator.analyze(
            build_request()
        )

    assert runtime.analyze_count == 0


def test_valid_request_reaches_runtime() -> None:
    runtime = HealthyRuntime()

    coordinator = VisualModelCoordinator(
        runtime=runtime,
        configuration=build_configuration(),
    )

    request = build_request()

    response = coordinator.analyze(
        request
    )

    assert (
        response.request_id
        == request.request_id
    )
    assert runtime.health_check_count == 1
    assert runtime.analyze_count == 1


def test_invalid_request_never_reaches_runtime() -> None:
    runtime = HealthyRuntime()

    coordinator = VisualModelCoordinator(
        runtime=runtime,
        configuration=build_configuration(),
    )

    with pytest.raises(
        VisualModelRequestValidationError,
        match="media_type is not allowed",
    ):
        coordinator.analyze(
            build_request(
                media_type=(
                    "image/jpeg"
                )
            )
        )

    assert runtime.health_check_count == 0
    assert runtime.analyze_count == 0


def test_unhealthy_runtime_prevents_inference() -> None:
    coordinator = VisualModelCoordinator(
        runtime=UnavailableRuntime(),
        configuration=build_configuration(),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="unavailable",
    ):
        coordinator.analyze(
            build_request()
        )


def test_health_check_can_be_skipped() -> None:
    runtime = HealthyRuntime()

    coordinator = VisualModelCoordinator(
        runtime=runtime,
        configuration=build_configuration(
            require_healthy_runtime=False
        ),
    )

    coordinator.analyze(
        build_request()
    )

    assert runtime.health_check_count == 0
    assert runtime.analyze_count == 1


def test_runtime_failure_is_wrapped() -> None:
    coordinator = VisualModelCoordinator(
        runtime=FailingRuntime(),
        configuration=build_configuration(),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="failed while processing",
    ):
        coordinator.analyze(
            build_request()
        )


def test_response_request_id_is_validated() -> None:
    coordinator = VisualModelCoordinator(
        runtime=WrongRequestRuntime(),
        configuration=build_configuration(),
    )

    with pytest.raises(
        VisualModelResponseValidationError,
        match="does not match",
    ):
        coordinator.analyze(
            build_request()
        )


def test_invalid_response_type_is_rejected() -> None:
    coordinator = VisualModelCoordinator(
        runtime=InvalidResponseRuntime(),
        configuration=build_configuration(),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="invalid response type",
    ):
        coordinator.analyze(
            build_request()
        )


def test_invalid_runtime_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="VisualModelRuntime",
    ):
        VisualModelCoordinator(
            runtime=object(),
            configuration=build_configuration(),
        )
