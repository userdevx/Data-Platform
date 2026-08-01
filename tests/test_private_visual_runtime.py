from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import pytest

from services.visual_model.errors import (
    VisualModelRuntimeError,
)
from services.visual_model.providers.private_runtime import (
    PrivateVisualBackendResult,
    PrivateVisualRuntime,
)
from services.visual_model.providers.runtime_config import (
    PRIVATE_VISUAL_RUNTIME_TYPE,
    PrivateVisualRuntimeConfiguration,
)
from services.visual_model.requests import (
    VisualModelRequest,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_model_file(
    tmp_path: Path,
) -> Path:
    model_path = (
        tmp_path / "model.bin"
    )

    model_path.write_bytes(
        b"runtime-model-file"
    )

    return model_path


def build_configuration(
    model_path: Path,
    *,
    enabled: bool = True,
) -> PrivateVisualRuntimeConfiguration:
    return PrivateVisualRuntimeConfiguration(
        enabled=enabled,
        runtime_type=(
            PRIVATE_VISUAL_RUNTIME_TYPE
        ),
        provider_name=(
            runtime_value("provider")
            if enabled
            else ""
        ),
        model_id=(
            runtime_value("model")
            if enabled
            else ""
        ),
        model_path=(
            str(model_path)
            if enabled
            else ""
        ),
        maximum_output_tokens=512,
        initialization_timeout_seconds=30,
        inference_timeout_seconds=20,
    )


def build_request() -> VisualModelRequest:
    return VisualModelRequest(
        request_id=runtime_value(
            "request"
        ),
        question=runtime_value(
            "question"
        ),
        image_data=b"runtime-image-data",
        media_type="image/png",
        response_schema={
            "type": "object",
        },
        source_reference=runtime_value(
            "source"
        ),
    )


class FakeBackend:
    def __init__(
        self,
        *,
        available: bool = True,
        fail_initialize: bool = False,
        fail_analyze: bool = False,
        invalid_result: bool = False,
    ) -> None:
        self.available = available
        self.fail_initialize = (
            fail_initialize
        )
        self.fail_analyze = fail_analyze
        self.invalid_result = invalid_result
        self.initialize_count = 0
        self.analyze_count = 0
        self.last_model_path: (
            Path | None
        ) = None

    def initialize(
        self,
        *,
        model_path: Path,
        model_id: str,
        initialization_timeout_seconds: int,
    ) -> None:
        del model_id
        del initialization_timeout_seconds

        self.initialize_count += 1
        self.last_model_path = model_path

        if self.fail_initialize:
            raise RuntimeError(
                "initialization failed"
            )

    def is_available(self) -> bool:
        return self.available

    def analyze(
        self,
        *,
        question: str,
        image_data: bytes,
        media_type: str,
        response_schema: Mapping[str, Any],
        maximum_output_tokens: int,
        inference_timeout_seconds: int,
    ) -> PrivateVisualBackendResult:
        del question
        del image_data
        del media_type
        del response_schema
        del maximum_output_tokens
        del inference_timeout_seconds

        self.analyze_count += 1

        if self.fail_analyze:
            raise RuntimeError(
                "inference failed"
            )

        if self.invalid_result:
            return {"invalid": True}  # type: ignore[return-value]

        return PrivateVisualBackendResult(
            scene_description=runtime_value(
                "scene"
            ),
            entities=(
                {
                    "entity_id": runtime_value(
                        "entity"
                    ),
                    "label": runtime_value(
                        "label"
                    ),
                    "confidence": 0.91,
                },
            ),
            uncertainty=(
                runtime_value("uncertainty"),
            ),
            metadata={
                "backend": "fake",
            },
        )


def test_runtime_is_lazy(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()

    PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=backend,
    )

    assert backend.initialize_count == 0


def test_health_check_initializes_once(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()

    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=backend,
    )

    first = runtime.health_check()
    second = runtime.health_check()

    assert first.available is True
    assert second.available is True
    assert backend.initialize_count == 1


def test_analyze_returns_correlated_response(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()

    configuration = build_configuration(
        create_model_file(tmp_path)
    )

    runtime = PrivateVisualRuntime(
        configuration=configuration,
        backend=backend,
    )

    request = build_request()
    response = runtime.analyze(request)

    assert (
        response.request_id
        == request.request_id
    )
    assert (
        response.provider
        == configuration.provider_name
    )
    assert (
        response.model_id
        == configuration.model_id
    )
    assert response.validation_passed is True
    assert len(response.entities) == 1
    assert response.duration_ms >= 0
    assert backend.initialize_count == 1
    assert backend.analyze_count == 1


def test_repeated_analysis_does_not_reinitialize(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()

    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=backend,
    )

    runtime.analyze(build_request())
    runtime.analyze(build_request())

    assert backend.initialize_count == 1
    assert backend.analyze_count == 2


def test_disabled_runtime_fails_closed(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()

    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            tmp_path / "unused.bin",
            enabled=False,
        ),
        backend=backend,
    )

    health = runtime.health_check()

    assert health.available is False

    with pytest.raises(
        VisualModelRuntimeError,
        match="disabled",
    ):
        runtime.analyze(
            build_request()
        )

    assert backend.initialize_count == 0


def test_missing_model_file_is_rejected(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            tmp_path / "missing.bin"
        ),
        backend=FakeBackend(),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="does not exist",
    ):
        runtime.analyze(
            build_request()
        )


def test_model_directory_is_rejected(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            tmp_path
        ),
        backend=FakeBackend(),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="must reference a file",
    ):
        runtime.analyze(
            build_request()
        )


def test_initialization_failure_is_wrapped(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=FakeBackend(
            fail_initialize=True
        ),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="could not initialize",
    ):
        runtime.analyze(
            build_request()
        )


def test_unavailable_backend_is_rejected(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=FakeBackend(
            available=False
        ),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="did not become available",
    ):
        runtime.analyze(
            build_request()
        )


def test_inference_failure_is_wrapped(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=FakeBackend(
            fail_analyze=True
        ),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="failed during inference",
    ):
        runtime.analyze(
            build_request()
        )


def test_invalid_backend_result_is_rejected(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=FakeBackend(
            invalid_result=True
        ),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="invalid result type",
    ):
        runtime.analyze(
            build_request()
        )


def test_response_contains_no_hidden_reasoning(
    tmp_path: Path,
) -> None:
    runtime = PrivateVisualRuntime(
        configuration=build_configuration(
            create_model_file(tmp_path)
        ),
        backend=FakeBackend(),
    )

    record = runtime.analyze(
        build_request()
    ).to_record()

    forbidden_fields = {
        "chain_of_thought",
        "hidden_reasoning",
        "reasoning_trace",
        "internal_reasoning",
    }

    assert forbidden_fields.isdisjoint(
        record
    )
