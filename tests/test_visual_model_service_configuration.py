from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from services.visual_model.config import (
    DEFAULT_ALLOWED_MEDIA_TYPES,
    DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES,
    VisualModelServiceConfiguration,
    load_visual_model_service_configuration,
    validate_visual_model_service_configuration,
)


def write_configuration(
    tmp_path: Path,
    payload: dict[str, Any],
) -> Path:
    path = (
        tmp_path
        / "visual-model-service.json"
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def build_payload() -> dict[str, Any]:
    return {
        "visual_model_service": {
            "enabled": True,
            "maximum_image_size_bytes": 4096,
            "allowed_media_types": [
                "image/png",
                "image/jpeg",
            ],
            "require_healthy_runtime": True,
        }
    }


def test_configuration_loads() -> None:
    configuration = (
        VisualModelServiceConfiguration()
    )

    assert configuration.enabled is False
    assert (
        configuration.maximum_image_size_bytes
        == DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES
    )
    assert (
        configuration.allowed_media_types
        == DEFAULT_ALLOWED_MEDIA_TYPES
    )
    assert (
        configuration.require_healthy_runtime
        is True
    )


def test_configuration_file_loads(
    tmp_path: Path,
) -> None:
    configuration = (
        load_visual_model_service_configuration(
            write_configuration(
                tmp_path,
                build_payload(),
            )
        )
    )

    assert configuration.enabled is True
    assert (
        configuration.maximum_image_size_bytes
        == 4096
    )
    assert configuration.allowed_media_types == (
        "image/png",
        "image/jpeg",
    )
    assert (
        configuration.require_healthy_runtime
        is True
    )


def test_media_types_are_normalized() -> None:
    configuration = (
        VisualModelServiceConfiguration(
            allowed_media_types=(
                " IMAGE/PNG ",
                "image/png",
                "image/webp",
            )
        )
    )

    assert configuration.allowed_media_types == (
        "image/png",
        "image/webp",
    )


def test_missing_optional_fields_use_defaults(
    tmp_path: Path,
) -> None:
    configuration = (
        load_visual_model_service_configuration(
            write_configuration(
                tmp_path,
                {
                    "visual_model_service": {
                        "enabled": False,
                    }
                },
            )
        )
    )

    assert (
        configuration.maximum_image_size_bytes
        == DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES
    )
    assert (
        configuration.allowed_media_types
        == DEFAULT_ALLOWED_MEDIA_TYPES
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        0,
        -1,
    ],
)
def test_image_size_must_be_positive(
    invalid_value: int,
) -> None:
    configuration = (
        VisualModelServiceConfiguration(
            maximum_image_size_bytes=(
                invalid_value
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="must be positive",
    ):
        validate_visual_model_service_configuration(
            configuration
        )


def test_media_type_list_cannot_be_empty() -> None:
    configuration = (
        VisualModelServiceConfiguration(
            allowed_media_types=()
        )
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        validate_visual_model_service_configuration(
            configuration
        )


@pytest.mark.parametrize(
    "media_type",
    [
        "invalid",
        "application/octet-stream",
        "text/plain",
    ],
)
def test_non_image_media_types_are_rejected(
    media_type: str,
) -> None:
    configuration = (
        VisualModelServiceConfiguration(
            allowed_media_types=(
                media_type,
            )
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Invalid media type"
            "|Unsupported media type"
        ),
    ):
        validate_visual_model_service_configuration(
            configuration
        )


def test_enabled_must_be_boolean(
    tmp_path: Path,
) -> None:
    payload = build_payload()

    payload[
        "visual_model_service"
    ]["enabled"] = "true"

    with pytest.raises(
        ValueError,
        match="must be a boolean",
    ):
        load_visual_model_service_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )


def test_allowed_media_types_must_be_array(
    tmp_path: Path,
) -> None:
    payload = build_payload()

    payload[
        "visual_model_service"
    ]["allowed_media_types"] = "image/png"

    with pytest.raises(
        ValueError,
        match="must be an array",
    ):
        load_visual_model_service_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )
