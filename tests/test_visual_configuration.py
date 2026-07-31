from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from engine.intelligence.vision.config import (
    ProviderRuntimeConfiguration,
    SamplingConfiguration,
    StorageConfiguration,
    ValidationConfiguration,
    VisualConfiguration,
    load_visual_configuration,
    validate_visual_configuration,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_payload(
    *,
    enabled: bool,
) -> dict[str, Any]:
    return {
        "visual_analysis": {
            "enabled": enabled,
            "provider": (
                runtime_value("provider")
                if enabled
                else ""
            ),
            "model": (
                runtime_value("model")
                if enabled
                else ""
            ),
            "provider_runtime": {
                "endpoint_url": (
                    "http://127.0.0.1:1/runtime"
                    if enabled
                    else ""
                ),
                "api_key_environment_variable": (
                    runtime_value("api-key-variable")
                    if enabled
                    else ""
                ),
                "request_timeout_seconds": 30,
                "maximum_output_tokens": 1024,
            },
            "maximum_media_size_bytes": 1024,
            "sampling": {
                "minimum_interval_ms": 1,
                "maximum_interval_ms": 1000,
                "analyze_on_change": True,
                "maximum_pending_frames": 1,
            },
            "validation": {
                "minimum_entity_confidence": 0.0,
                "minimum_relation_confidence": 0.0,
                "minimum_temporal_frames": 2,
            },
            "storage": {
                "store_raw_frames": False,
                "store_provider_responses": False,
                "store_validated_observations": True,
            },
        }
    }


def write_configuration(
    tmp_path: Path,
    payload: dict[str, Any],
) -> Path:
    path = tmp_path / "visual-configuration.json"
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def build_configuration(
    *,
    enabled: bool,
) -> VisualConfiguration:
    return VisualConfiguration(
        enabled=enabled,
        provider=(
            runtime_value("provider")
            if enabled
            else ""
        ),
        model=(
            runtime_value("model")
            if enabled
            else ""
        ),
        maximum_media_size_bytes=1024,
        sampling=SamplingConfiguration(
            minimum_interval_ms=1,
            maximum_interval_ms=1000,
            analyze_on_change=True,
            maximum_pending_frames=1,
        ),
        validation=ValidationConfiguration(
            minimum_entity_confidence=0.0,
            minimum_relation_confidence=0.0,
            minimum_temporal_frames=2,
        ),
        storage=StorageConfiguration(
            store_raw_frames=False,
            store_provider_responses=False,
            store_validated_observations=True,
        ),
        provider_runtime=(
            ProviderRuntimeConfiguration(
                endpoint_url=(
                    "http://127.0.0.1:1/runtime"
                    if enabled
                    else ""
                ),
                api_key_environment_variable=(
                    runtime_value(
                        "api-key-variable"
                    )
                    if enabled
                    else ""
                ),
                request_timeout_seconds=30,
                maximum_output_tokens=1024,
            )
        ),
    )


def test_disabled_configuration_loads(
    tmp_path: Path,
) -> None:
    configuration = load_visual_configuration(
        write_configuration(
            tmp_path,
            build_payload(enabled=False),
        )
    )

    assert configuration.enabled is False
    assert configuration.provider == ""
    assert configuration.model == ""
    assert (
        configuration.provider_runtime.endpoint_url
        == ""
    )


def test_enabled_configuration_loads_provider_runtime(
    tmp_path: Path,
) -> None:
    payload = build_payload(enabled=True)

    configuration = load_visual_configuration(
        write_configuration(
            tmp_path,
            payload,
        )
    )

    root = payload["visual_analysis"]
    runtime = root["provider_runtime"]

    assert configuration.enabled is True
    assert configuration.provider == root["provider"]
    assert configuration.model == root["model"]
    assert (
        configuration.provider_runtime.endpoint_url
        == runtime["endpoint_url"]
    )
    assert (
        configuration.provider_runtime
        .api_key_environment_variable
        == runtime[
            "api_key_environment_variable"
        ]
    )
    assert (
        configuration.provider_runtime
        .request_timeout_seconds
        == runtime["request_timeout_seconds"]
    )
    assert (
        configuration.provider_runtime
        .maximum_output_tokens
        == runtime["maximum_output_tokens"]
    )


def test_missing_provider_runtime_uses_defaults(
    tmp_path: Path,
) -> None:
    payload = build_payload(enabled=False)

    payload["visual_analysis"].pop(
        "provider_runtime"
    )

    configuration = load_visual_configuration(
        write_configuration(
            tmp_path,
            payload,
        )
    )

    assert configuration.provider_runtime == (
        ProviderRuntimeConfiguration()
    )


@pytest.mark.parametrize(
    ("field_name", "expected_message"),
    [
        (
            "provider",
            "requires a provider",
        ),
        (
            "model",
            "requires a model",
        ),
    ],
)
def test_enabled_configuration_requires_core_fields(
    field_name: str,
    expected_message: str,
    tmp_path: Path,
) -> None:
    payload = build_payload(enabled=True)
    payload["visual_analysis"][field_name] = ""

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        load_visual_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )


@pytest.mark.parametrize(
    ("field_name", "expected_message"),
    [
        (
            "endpoint_url",
            "endpoint URL",
        ),
        (
            "api_key_environment_variable",
            "environment-variable name",
        ),
    ],
)
def test_enabled_configuration_requires_runtime_fields(
    field_name: str,
    expected_message: str,
    tmp_path: Path,
) -> None:
    payload = build_payload(enabled=True)

    payload[
        "visual_analysis"
    ][
        "provider_runtime"
    ][field_name] = ""

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        load_visual_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        (
            "request_timeout_seconds",
            0,
            "request_timeout_seconds",
        ),
        (
            "maximum_output_tokens",
            0,
            "maximum_output_tokens",
        ),
    ],
)
def test_runtime_limits_must_be_positive(
    field_name: str,
    invalid_value: int,
    message: str,
    tmp_path: Path,
) -> None:
    payload = build_payload(enabled=False)

    payload[
        "visual_analysis"
    ][
        "provider_runtime"
    ][field_name] = invalid_value

    with pytest.raises(
        ValueError,
        match=message,
    ):
        load_visual_configuration(
            write_configuration(
                tmp_path,
                payload,
            )
        )


def test_direct_disabled_configuration_remains_valid() -> None:
    validate_visual_configuration(
        build_configuration(
            enabled=False
        )
    )


def test_direct_enabled_configuration_is_valid() -> None:
    validate_visual_configuration(
        build_configuration(
            enabled=True
        )
    )
