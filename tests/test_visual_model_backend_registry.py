from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from services.visual_model.backend_registry import (
    PrivateVisualBackendRegistry,
)
from services.visual_model.errors import (
    VisualModelBackendRegistrationError,
)
from services.visual_model.providers.private_runtime import (
    PrivateVisualBackendResult,
)


class CompatibleBackend:
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


def test_backend_can_be_registered_and_created() -> None:
    registry = PrivateVisualBackendRegistry()

    registry.register(
        backend_name="runtime-backend",
        factory=CompatibleBackend,
    )

    backend = registry.create(
        "runtime-backend"
    )

    assert isinstance(
        backend,
        CompatibleBackend,
    )


def test_backend_names_are_normalized() -> None:
    registry = PrivateVisualBackendRegistry()

    registry.register(
        backend_name=" Runtime-Backend ",
        factory=CompatibleBackend,
    )

    assert registry.registered_names() == (
        "runtime-backend",
    )

    assert registry.contains(
        " RUNTIME-BACKEND "
    )


def test_duplicate_backend_is_rejected() -> None:
    registry = PrivateVisualBackendRegistry()

    registry.register(
        backend_name="runtime-backend",
        factory=CompatibleBackend,
    )

    with pytest.raises(
        VisualModelBackendRegistrationError,
        match="already registered",
    ):
        registry.register(
            backend_name="runtime-backend",
            factory=CompatibleBackend,
        )


def test_unknown_backend_is_rejected() -> None:
    registry = PrivateVisualBackendRegistry()

    with pytest.raises(
        VisualModelBackendRegistrationError,
        match="not registered",
    ):
        registry.create(
            "unknown-backend"
        )


def test_incompatible_backend_is_rejected() -> None:
    registry = PrivateVisualBackendRegistry()

    registry.register(
        backend_name="invalid-backend",
        factory=object,
    )

    with pytest.raises(
        VisualModelBackendRegistrationError,
        match="incompatible",
    ):
        registry.create(
            "invalid-backend"
        )


def test_backend_can_be_unregistered() -> None:
    registry = PrivateVisualBackendRegistry()

    registry.register(
        backend_name="runtime-backend",
        factory=CompatibleBackend,
    )

    assert registry.unregister(
        "runtime-backend"
    )

    assert not registry.contains(
        "runtime-backend"
    )


def test_empty_backend_name_is_rejected() -> None:
    registry = PrivateVisualBackendRegistry()

    with pytest.raises(
        VisualModelBackendRegistrationError,
        match="required",
    ):
        registry.register(
            backend_name="",
            factory=CompatibleBackend,
        )
