from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from services.visual_model.backend_registry import (
    PrivateVisualBackendRegistry,
)
from services.visual_model.bootstrap import (
    assemble_visual_model_service,
    load_visual_model_bootstrap_configuration,
)
from services.visual_model.errors import (
    VisualModelBootstrapError,
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


def write_json(
    path: Path,
    value: dict,
) -> Path:
    path.write_text(
        json.dumps(value),
        encoding="utf-8",
    )

    return path


def write_runtime_configuration(
    tmp_path: Path,
    *,
    enabled: bool,
    model_path: str = "",
) -> Path:
    return write_json(
        tmp_path / "runtime.json",
        {
            "private_visual_runtime": {
                "enabled": enabled,
                "runtime_type": (
                    "private_visual_runtime"
                ),
                "provider_name": (
                    "runtime-provider"
                    if enabled
                    else ""
                ),
                "model_id": (
                    "runtime-model"
                    if enabled
                    else ""
                ),
                "model_path": (
                    model_path
                    if enabled
                    else ""
                ),
                "maximum_output_tokens": 256,
                "initialization_timeout_seconds": 10,
                "inference_timeout_seconds": 10,
            }
        },
    )


def write_service_configuration(
    tmp_path: Path,
    *,
    enabled: bool,
    backend_name: str,
) -> Path:
    return write_json(
        tmp_path / "service.json",
        {
            "visual_model_service": {
                "enabled": enabled,
                "maximum_image_size_bytes": 4096,
                "allowed_media_types": [
                    "image/png"
                ],
                "require_healthy_runtime": True,
            },
            "visual_model_transport": {
                "backend_name": backend_name,
                "host": "127.0.0.1",
                "port": 0,
                "service_path": "/runtime",
                "maximum_request_payload_size_bytes": 8192,
                "maximum_response_payload_size_bytes": 8192,
            },
        },
    )


def test_bootstrap_configuration_loads(
    tmp_path: Path,
) -> None:
    path = write_service_configuration(
        tmp_path,
        enabled=False,
        backend_name="",
    )

    configuration = (
        load_visual_model_bootstrap_configuration(
            path
        )
    )

    assert configuration.host == "127.0.0.1"
    assert configuration.port == 0
    assert (
        configuration.service_path
        == "/runtime"
    )


def test_disabled_service_assembles_without_backend(
    tmp_path: Path,
) -> None:
    assembly = assemble_visual_model_service(
        backend_registry=(
            PrivateVisualBackendRegistry()
        ),
        runtime_configuration_path=(
            write_runtime_configuration(
                tmp_path,
                enabled=False,
            )
        ),
        service_configuration_path=(
            write_service_configuration(
                tmp_path,
                enabled=False,
                backend_name="",
            )
        ),
    )

    assert (
        assembly.runtime_configuration.enabled
        is False
    )
    assert (
        assembly.service_configuration.enabled
        is False
    )
    assert (
        assembly.transport_configuration.host
        == "127.0.0.1"
    )


def test_enabled_service_uses_registered_backend(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(
        b"model-data"
    )

    registry = PrivateVisualBackendRegistry()

    registry.register(
        backend_name="runtime-backend",
        factory=CompatibleBackend,
    )

    assembly = assemble_visual_model_service(
        backend_registry=registry,
        runtime_configuration_path=(
            write_runtime_configuration(
                tmp_path,
                enabled=True,
                model_path=str(model_path),
            )
        ),
        service_configuration_path=(
            write_service_configuration(
                tmp_path,
                enabled=True,
                backend_name="runtime-backend",
            )
        ),
    )

    health = assembly.coordinator.health_check()

    assert health.available is True


def test_unknown_enabled_backend_fails_bootstrap(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(
        b"model-data"
    )

    with pytest.raises(
        VisualModelBootstrapError,
        match="could not be created",
    ):
        assemble_visual_model_service(
            backend_registry=(
                PrivateVisualBackendRegistry()
            ),
            runtime_configuration_path=(
                write_runtime_configuration(
                    tmp_path,
                    enabled=True,
                    model_path=str(
                        model_path
                    ),
                )
            ),
            service_configuration_path=(
                write_service_configuration(
                    tmp_path,
                    enabled=True,
                    backend_name=(
                        "unknown-backend"
                    ),
                )
            ),
        )


def test_public_bind_is_rejected(
    tmp_path: Path,
) -> None:
    service_path = write_service_configuration(
        tmp_path,
        enabled=False,
        backend_name="",
    )

    payload = json.loads(
        service_path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "visual_model_transport"
    ]["host"] = "0.0.0.0"

    write_json(
        service_path,
        payload,
    )

    with pytest.raises(
        VisualModelBootstrapError,
    ):
        assemble_visual_model_service(
            backend_registry=(
                PrivateVisualBackendRegistry()
            ),
            runtime_configuration_path=(
                write_runtime_configuration(
                    tmp_path,
                    enabled=False,
                )
            ),
            service_configuration_path=(
                service_path
            ),
        )
