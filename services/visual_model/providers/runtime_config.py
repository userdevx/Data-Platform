from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PRIVATE_VISUAL_RUNTIME_TYPE = "private_visual_runtime"

DEFAULT_MAXIMUM_OUTPUT_TOKENS = 1024
DEFAULT_INITIALIZATION_TIMEOUT_SECONDS = 120
DEFAULT_INFERENCE_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class PrivateVisualRuntimeConfiguration:
    enabled: bool = False
    runtime_type: str = PRIVATE_VISUAL_RUNTIME_TYPE
    provider_name: str = ""
    model_id: str = ""
    model_path: str = ""
    maximum_output_tokens: int = DEFAULT_MAXIMUM_OUTPUT_TOKENS
    initialization_timeout_seconds: int = (
        DEFAULT_INITIALIZATION_TIMEOUT_SECONDS
    )
    inference_timeout_seconds: int = (
        DEFAULT_INFERENCE_TIMEOUT_SECONDS
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "runtime_type",
            self.runtime_type.strip(),
        )
        object.__setattr__(
            self,
            "provider_name",
            self.provider_name.strip(),
        )
        object.__setattr__(
            self,
            "model_id",
            self.model_id.strip(),
        )
        object.__setattr__(
            self,
            "model_path",
            self.model_path.strip(),
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


def _require_integer(
    value: Any,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be an integer."
        ) from error


def validate_private_visual_runtime_configuration(
    configuration: PrivateVisualRuntimeConfiguration,
) -> None:
    if not configuration.runtime_type:
        raise ValueError(
            "runtime_type is required."
        )

    if (
        configuration.runtime_type
        != PRIVATE_VISUAL_RUNTIME_TYPE
    ):
        raise ValueError(
            "Unsupported private visual runtime type."
        )

    if configuration.maximum_output_tokens < 1:
        raise ValueError(
            "maximum_output_tokens must be positive."
        )

    if (
        configuration.initialization_timeout_seconds
        < 1
    ):
        raise ValueError(
            "initialization_timeout_seconds "
            "must be positive."
        )

    if (
        configuration.inference_timeout_seconds
        < 1
    ):
        raise ValueError(
            "inference_timeout_seconds "
            "must be positive."
        )

    if not configuration.enabled:
        return

    if not configuration.provider_name:
        raise ValueError(
            "An enabled private visual runtime "
            "requires provider_name."
        )

    if not configuration.model_id:
        raise ValueError(
            "An enabled private visual runtime "
            "requires model_id."
        )

    if not configuration.model_path:
        raise ValueError(
            "An enabled private visual runtime "
            "requires model_path."
        )


def load_private_visual_runtime_configuration(
    path: Path,
) -> PrivateVisualRuntimeConfiguration:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    root = _require_mapping(
        payload.get("private_visual_runtime"),
        field_name="private_visual_runtime",
    )

    configuration = PrivateVisualRuntimeConfiguration(
        enabled=_require_boolean(
            root.get("enabled", False),
            field_name=(
                "private_visual_runtime.enabled"
            ),
        ),
        runtime_type=str(
            root.get(
                "runtime_type",
                PRIVATE_VISUAL_RUNTIME_TYPE,
            )
        ),
        provider_name=str(
            root.get("provider_name", "")
        ),
        model_id=str(
            root.get("model_id", "")
        ),
        model_path=str(
            root.get("model_path", "")
        ),
        maximum_output_tokens=_require_integer(
            root.get(
                "maximum_output_tokens",
                DEFAULT_MAXIMUM_OUTPUT_TOKENS,
            ),
            field_name=(
                "private_visual_runtime."
                "maximum_output_tokens"
            ),
        ),
        initialization_timeout_seconds=(
            _require_integer(
                root.get(
                    "initialization_timeout_seconds",
                    DEFAULT_INITIALIZATION_TIMEOUT_SECONDS,
                ),
                field_name=(
                    "private_visual_runtime."
                    "initialization_timeout_seconds"
                ),
            )
        ),
        inference_timeout_seconds=_require_integer(
            root.get(
                "inference_timeout_seconds",
                DEFAULT_INFERENCE_TIMEOUT_SECONDS,
            ),
            field_name=(
                "private_visual_runtime."
                "inference_timeout_seconds"
            ),
        ),
    )

    validate_private_visual_runtime_configuration(
        configuration
    )

    return configuration
