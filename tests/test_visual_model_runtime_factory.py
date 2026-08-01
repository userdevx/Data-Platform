from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

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
from services.visual_model.runtime_factory import (
    build_visual_model_runtime,
)


class FactoryBackend:
    def initialize(
        self,
        *,
        model_path: Path,
        model_id: str,
        initialization_timeout_seconds: int,
    ) -> None:
        del model_path
        del model_id
        del initialization_timeout_seconds

    def is_available(self) -> bool:
        return True

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

        return PrivateVisualBackendResult(
            scene_description="runtime result"
        )


def build_configuration(
    *,
    runtime_type: str = (
        PRIVATE_VISUAL_RUNTIME_TYPE
    ),
) -> PrivateVisualRuntimeConfiguration:
    return PrivateVisualRuntimeConfiguration(
        enabled=False,
        runtime_type=runtime_type,
    )


def test_factory_builds_private_runtime() -> None:
    runtime = build_visual_model_runtime(
        configuration=build_configuration(),
        backend_factory=FactoryBackend,
    )

    assert isinstance(
        runtime,
        PrivateVisualRuntime,
    )


def test_factory_creates_backend_once() -> None:
    creation_count = 0

    def create_backend() -> FactoryBackend:
        nonlocal creation_count
        creation_count += 1
        return FactoryBackend()

    build_visual_model_runtime(
        configuration=build_configuration(),
        backend_factory=create_backend,
    )

    assert creation_count == 1


def test_backend_factory_failure_is_wrapped() -> None:
    def failing_factory():
        raise RuntimeError(
            "factory failed"
        )

    with pytest.raises(
        VisualModelRuntimeError,
        match="could not be created",
    ):
        build_visual_model_runtime(
            configuration=build_configuration(),
            backend_factory=failing_factory,
        )


def test_non_callable_factory_is_rejected() -> None:
    with pytest.raises(
        VisualModelRuntimeError,
        match="must be callable",
    ):
        build_visual_model_runtime(
            configuration=build_configuration(),
            backend_factory=object(),  # type: ignore[arg-type]
        )


def test_incompatible_backend_is_rejected() -> None:
    with pytest.raises(
        VisualModelRuntimeError,
        match="could not be constructed",
    ):
        build_visual_model_runtime(
            configuration=build_configuration(),
            backend_factory=object,
        )


def test_unknown_runtime_type_is_rejected() -> None:
    configuration = (
        PrivateVisualRuntimeConfiguration(
            enabled=False,
            runtime_type="unknown-runtime",
        )
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match=(
            "Unsupported private visual runtime type"
            "|not supported"
        ),
    ):
        build_visual_model_runtime(
            configuration=configuration,
            backend_factory=FactoryBackend,
        )
