from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.visual_model.backend_registration import (
    LOCAL_PROCESS_VISUAL_BACKEND_NAME,
    VisualBackendRegistrationConfiguration,
    load_backend_registration_configuration,
    register_configured_visual_backend,
)
from services.visual_model.backend_registry import (
    PrivateVisualBackendRegistry,
)
from services.visual_model.providers.local_process_backend import (
    LocalProcessVisualBackend,
)


def write_configuration(
    tmp_path: Path,
    payload: dict,
) -> Path:
    path = tmp_path / "backend.json"

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def build_payload(
    *,
    enabled: bool,
    executable_path: str = "",
) -> dict:
    return {
        "visual_backend": {
            "enabled": enabled,
            "backend_name": (
                LOCAL_PROCESS_VISUAL_BACKEND_NAME
            ),
            "executable_path": (
                executable_path
            ),
            "arguments": [],
            "working_directory": "",
            "environment": {},
            "maximum_response_size_bytes": 4096,
        }
    }


def test_disabled_backend_configuration_loads(
    tmp_path: Path,
) -> None:
    configuration = (
        load_backend_registration_configuration(
            write_configuration(
                tmp_path,
                build_payload(
                    enabled=False
                ),
            )
        )
    )

    assert configuration.enabled is False


def test_enabled_backend_requires_executable(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="requires executable_path",
    ):
        load_backend_registration_configuration(
            write_configuration(
                tmp_path,
                build_payload(
                    enabled=True,
                    executable_path="",
                ),
            )
        )


def test_disabled_backend_is_not_registered() -> None:
    registry = PrivateVisualBackendRegistry()

    register_configured_visual_backend(
        registry=registry,
        configuration=(
            VisualBackendRegistrationConfiguration(
                enabled=False,
                backend_name=(
                    LOCAL_PROCESS_VISUAL_BACKEND_NAME
                ),
                executable_path="",
                arguments=(),
                working_directory="",
                environment={},
                maximum_response_size_bytes=4096,
            )
        ),
    )

    assert registry.registered_names() == ()


def test_enabled_backend_is_registered(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "backend"
    executable.write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )

    registry = PrivateVisualBackendRegistry()

    register_configured_visual_backend(
        registry=registry,
        configuration=(
            VisualBackendRegistrationConfiguration(
                enabled=True,
                backend_name=(
                    LOCAL_PROCESS_VISUAL_BACKEND_NAME
                ),
                executable_path=str(
                    executable
                ),
                arguments=(),
                working_directory="",
                environment={},
                maximum_response_size_bytes=4096,
            )
        ),
    )

    assert registry.registered_names() == (
        LOCAL_PROCESS_VISUAL_BACKEND_NAME,
    )

    backend = registry.create(
        LOCAL_PROCESS_VISUAL_BACKEND_NAME
    )

    assert isinstance(
        backend,
        LocalProcessVisualBackend,
    )


def test_unknown_backend_name_is_rejected() -> None:
    configuration = (
        VisualBackendRegistrationConfiguration(
            enabled=True,
            backend_name="unknown-backend",
            executable_path="/tmp/backend",
            arguments=(),
            working_directory="",
            environment={},
            maximum_response_size_bytes=4096,
        )
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        register_configured_visual_backend(
            registry=(
                PrivateVisualBackendRegistry()
            ),
            configuration=configuration,
        )
