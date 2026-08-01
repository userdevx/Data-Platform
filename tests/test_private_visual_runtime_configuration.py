from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from services.visual_model.providers.runtime_config import (
    PRIVATE_VISUAL_RUNTIME_TYPE,
    PrivateVisualRuntimeConfiguration,
    load_private_visual_runtime_configuration,
    validate_private_visual_runtime_configuration,
)


def write_configuration(
    tmp_path: Path,
    payload: dict[str, Any],
) -> Path:
    path = (
        tmp_path
        / "private-visual-runtime.json"
    )

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def build_payload(
    *,
    enabled: bool,
    model_path: str = "",
) -> dict[str, Any]:
    return {
        "private_visual_runtime": {
            "enabled": enabled,
            "runtime_type": (
                PRIVATE_VISUAL_RUNTIME_TYPE
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
            "maximum_output_tokens": 1024,
            "initialization_timeout_seconds": 120,
            "inference_timeout_seconds": 60,
        }
    }


def test_disabled_configuration_loads(
    tmp_path: Path,
) -> None:
    configuration = (
        load_private_visual_runtime_configuration(
            write_configuration(
                tmp_path,
                build_payload(
                    enabled=False
                ),
            )
        )
    )

    assert configuration.enabled is False
    assert configuration.provider_name == ""
    assert configuration.model_id == ""
    assert configuration.model_path == ""


def test_enabled_configuration_loads(
    tmp_path: Path,
) -> None:
    model_path = str(
        tmp_path / "model.bin"
    )

    configuration = (
        load_private_visual_runtime_configuration(
            write_configuration(
                tmp_path,
                build_payload(
                    enabled=True,
                    model_path=model_path,
                ),
            )
        )
    )

    assert configuration.enabled is True
    assert (
        configuration.runtime_type
        == PRIVATE_VISUAL_RUNTIME_TYPE
    )
    assert (
        configuration.model_path
        == model_path
    )


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        (
            "provider_name",
            "requires provider_name",
        ),
        (
            "model_id",
            "requires model_id",
        ),
        (
            "model_path",
            "requires model_path",
        ),
    ],
)
def test_enabled_configuration_requires_fields(
    field_name: str,
    message: str,
    tmp_path: Path,
) -> None:
    payload = build_payload(
        enabled=True,
        model_path=str(
            tmp_path / "model.bin"
        ),
    )

    payload[
        "private_visual_runtime"
    ][field_name] = ""

    with pytest.raises(
        ValueError,
        match=message,
    ):
        load_private_visual_runtime_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "maximum_output_tokens",
        "initialization_timeout_seconds",
        "inference_timeout_seconds",
    ],
)
def test_positive_limits_are_required(
    field_name: str,
) -> None:
    values = {
        "enabled": False,
        "runtime_type": (
            PRIVATE_VISUAL_RUNTIME_TYPE
        ),
        "provider_name": "",
        "model_id": "",
        "model_path": "",
        "maximum_output_tokens": 1024,
        "initialization_timeout_seconds": 120,
        "inference_timeout_seconds": 60,
    }

    values[field_name] = 0

    configuration = (
        PrivateVisualRuntimeConfiguration(
            **values
        )
    )

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        validate_private_visual_runtime_configuration(
            configuration
        )


def test_unknown_runtime_type_is_rejected() -> None:
    configuration = (
        PrivateVisualRuntimeConfiguration(
            runtime_type="unknown-runtime"
        )
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        validate_private_visual_runtime_configuration(
            configuration
        )


def test_enabled_must_be_boolean(
    tmp_path: Path,
) -> None:
    payload = build_payload(
        enabled=False
    )

    payload[
        "private_visual_runtime"
    ]["enabled"] = "false"

    with pytest.raises(
        ValueError,
        match="must be a boolean",
    ):
        load_private_visual_runtime_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )
