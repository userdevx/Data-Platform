from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES = 15 * 1024 * 1024

DEFAULT_ALLOWED_MEDIA_TYPES = (
    "image/jpeg",
    "image/png",
    "image/webp",
)


@dataclass(frozen=True)
class VisualModelServiceConfiguration:
    enabled: bool = False
    maximum_image_size_bytes: int = (
        DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES
    )
    allowed_media_types: tuple[str, ...] = (
        DEFAULT_ALLOWED_MEDIA_TYPES
    )
    require_healthy_runtime: bool = True

    def __post_init__(self) -> None:
        normalized_media_types = tuple(
            dict.fromkeys(
                media_type.strip().lower()
                for media_type in self.allowed_media_types
                if media_type.strip()
            )
        )

        object.__setattr__(
            self,
            "allowed_media_types",
            normalized_media_types,
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
        parsed_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be an integer."
        ) from error

    return parsed_value


def _require_media_types(
    value: Any,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(
            "allowed_media_types must be an array."
        )

    media_types: list[str] = []

    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(
                "allowed_media_types"
                f"[{index}] must be text."
            )

        normalized = item.strip().lower()

        if normalized:
            media_types.append(normalized)

    return tuple(
        dict.fromkeys(media_types)
    )


def validate_visual_model_service_configuration(
    configuration: VisualModelServiceConfiguration,
) -> None:
    if configuration.maximum_image_size_bytes < 1:
        raise ValueError(
            "maximum_image_size_bytes must be positive."
        )

    if not configuration.allowed_media_types:
        raise ValueError(
            "allowed_media_types cannot be empty."
        )

    for media_type in configuration.allowed_media_types:
        if "/" not in media_type:
            raise ValueError(
                f"Invalid media type: {media_type}"
            )

        category, subtype = media_type.split(
            "/",
            maxsplit=1,
        )

        if category != "image" or not subtype:
            raise ValueError(
                f"Unsupported media type: {media_type}"
            )


def load_visual_model_service_configuration(
    path: Path,
) -> VisualModelServiceConfiguration:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    root = _require_mapping(
        payload.get("visual_model_service"),
        field_name="visual_model_service",
    )

    configuration = VisualModelServiceConfiguration(
        enabled=_require_boolean(
            root.get("enabled", False),
            field_name=(
                "visual_model_service.enabled"
            ),
        ),
        maximum_image_size_bytes=_require_integer(
            root.get(
                "maximum_image_size_bytes",
                DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES,
            ),
            field_name=(
                "visual_model_service."
                "maximum_image_size_bytes"
            ),
        ),
        allowed_media_types=_require_media_types(
            root.get(
                "allowed_media_types",
                list(DEFAULT_ALLOWED_MEDIA_TYPES),
            )
        ),
        require_healthy_runtime=_require_boolean(
            root.get(
                "require_healthy_runtime",
                True,
            ),
            field_name=(
                "visual_model_service."
                "require_healthy_runtime"
            ),
        ),
    )

    validate_visual_model_service_configuration(
        configuration
    )

    return configuration
