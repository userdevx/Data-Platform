from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.visual_model.backend_registry import (
    PrivateVisualBackendRegistry,
)
from services.visual_model.errors import (
    VisualModelBackendRegistrationError,
)
from services.visual_model.providers.local_process_backend import (
    LocalProcessVisualBackend,
    LocalProcessVisualBackendConfiguration,
)


LOCAL_PROCESS_VISUAL_BACKEND_NAME = (
    "local_process_visual_backend"
)


@dataclass(frozen=True)
class VisualBackendRegistrationConfiguration:
    enabled: bool
    backend_name: str
    executable_path: str
    arguments: tuple[str, ...]
    working_directory: str
    environment: dict[str, str]
    maximum_response_size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "backend_name",
            self.backend_name.strip().lower(),
        )
        object.__setattr__(
            self,
            "executable_path",
            self.executable_path.strip(),
        )
        object.__setattr__(
            self,
            "working_directory",
            self.working_directory.strip(),
        )


def _require_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{field_name} must be an object."
        )

    return value


def _require_boolean(
    value: Any,
    *,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be a boolean."
        )

    return value


def _require_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be text."
        )

    return value


def _require_integer(
    value: Any,
    *,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    return value


def _require_arguments(
    value: Any,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(
            "arguments must be an array."
        )

    result: list[str] = []

    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(
                f"arguments[{index}] must be text."
            )

        result.append(item)

    return tuple(result)


def _require_environment(
    value: Any,
) -> dict[str, str]:
    mapping = _require_mapping(
        value,
        field_name="environment",
    )

    result: dict[str, str] = {}

    for key, item in mapping.items():
        if not isinstance(
            key,
            str,
        ) or not isinstance(
            item,
            str,
        ):
            raise ValueError(
                "environment keys and values "
                "must be text."
            )

        result[key] = item

    return result


def validate_backend_registration_configuration(
    configuration: (
        VisualBackendRegistrationConfiguration
    ),
) -> None:
    if (
        configuration
        .maximum_response_size_bytes
        < 1
    ):
        raise ValueError(
            "maximum_response_size_bytes "
            "must be positive."
        )

    if not configuration.enabled:
        return

    if (
        configuration.backend_name
        != LOCAL_PROCESS_VISUAL_BACKEND_NAME
    ):
        raise ValueError(
            "Unsupported visual backend name."
        )

    if not configuration.executable_path:
        raise ValueError(
            "An enabled local-process backend "
            "requires executable_path."
        )


def load_backend_registration_configuration(
    path: Path,
) -> VisualBackendRegistrationConfiguration:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    root = _require_mapping(
        payload.get("visual_backend"),
        field_name="visual_backend",
    )

    configuration = (
        VisualBackendRegistrationConfiguration(
            enabled=_require_boolean(
                root.get("enabled", False),
                field_name=(
                    "visual_backend.enabled"
                ),
            ),
            backend_name=_require_text(
                root.get(
                    "backend_name",
                    LOCAL_PROCESS_VISUAL_BACKEND_NAME,
                ),
                field_name=(
                    "visual_backend.backend_name"
                ),
            ),
            executable_path=_require_text(
                root.get(
                    "executable_path",
                    "",
                ),
                field_name=(
                    "visual_backend."
                    "executable_path"
                ),
            ),
            arguments=_require_arguments(
                root.get("arguments", [])
            ),
            working_directory=_require_text(
                root.get(
                    "working_directory",
                    "",
                ),
                field_name=(
                    "visual_backend."
                    "working_directory"
                ),
            ),
            environment=_require_environment(
                root.get(
                    "environment",
                    {},
                )
            ),
            maximum_response_size_bytes=(
                _require_integer(
                    root.get(
                        (
                            "maximum_response_"
                            "size_bytes"
                        ),
                        10 * 1024 * 1024,
                    ),
                    field_name=(
                        "visual_backend."
                        "maximum_response_size_bytes"
                    ),
                )
            ),
        )
    )

    validate_backend_registration_configuration(
        configuration
    )

    return configuration


def register_configured_visual_backend(
    *,
    registry: PrivateVisualBackendRegistry,
    configuration: (
        VisualBackendRegistrationConfiguration
    ),
) -> None:
    validate_backend_registration_configuration(
        configuration
    )

    if not configuration.enabled:
        return

    try:
        backend_configuration = (
            LocalProcessVisualBackendConfiguration(
                executable_path=(
                    configuration
                    .executable_path
                ),
                arguments=(
                    configuration.arguments
                ),
                working_directory=(
                    configuration
                    .working_directory
                ),
                environment=(
                    configuration.environment
                ),
                maximum_response_size_bytes=(
                    configuration
                    .maximum_response_size_bytes
                ),
            )
        )

        registry.register(
            backend_name=(
                configuration.backend_name
            ),
            factory=lambda: (
                LocalProcessVisualBackend(
                    configuration=(
                        backend_configuration
                    )
                )
            ),
        )
    except (
        ValueError,
        VisualModelBackendRegistrationError,
    ):
        raise
    except Exception as error:
        raise VisualModelBackendRegistrationError(
            "The configured local visual backend "
            "could not be registered."
        ) from error
