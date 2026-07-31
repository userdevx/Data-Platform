from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from engine.intelligence.vision.application_bridge import (
    analyze_image,
    configuration_to_record,
    get_visual_status,
)
from engine.intelligence.vision.config import (
    ProviderRuntimeConfiguration,
    SamplingConfiguration,
    StorageConfiguration,
    ValidationConfiguration,
    VisualConfiguration,
)
from engine.intelligence.vision.models import (
    VisualEntity,
    VisualObservation,
)
from engine.intelligence.vision.provider_factory import (
    REMOTE_VISUAL_PROVIDER_TYPE,
    VisualProviderConfigurationError,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_configuration_payload(
    *,
    enabled: bool,
    provider: str,
) -> dict[str, Any]:
    return {
        "visual_analysis": {
            "enabled": enabled,
            "provider": provider,
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
                    runtime_value(
                        "credential-environment-variable"
                    )
                    if enabled
                    else ""
                ),
                "request_timeout_seconds": 30,
                "maximum_output_tokens": 1024,
            },
            "maximum_media_size_bytes": 1024 * 1024,
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


def write_image(
    tmp_path: Path,
) -> Path:
    image_bytes = base64.b64decode(
        (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
            "CAQAAAC1HAwCAAAAC0lEQVR42mP8"
            "/x8AAusB9Y9Z4mAAAAAASUVORK5CYII="
        )
    )

    path = tmp_path / "runtime-image.png"
    path.write_bytes(image_bytes)
    return path


def direct_configuration() -> VisualConfiguration:
    return VisualConfiguration(
        enabled=True,
        provider=REMOTE_VISUAL_PROVIDER_TYPE,
        model=runtime_value("model"),
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
                ),
                api_key_environment_variable=(
                    runtime_value(
                        "credential-environment-variable"
                    )
                ),
                request_timeout_seconds=30,
                maximum_output_tokens=1024,
            )
        ),
    )


class GeneratedAnalyzer:
    def analyze(
        self,
        *,
        request,
        frame,
    ) -> VisualObservation:
        return VisualObservation(
            observation_id=runtime_value(
                "observation"
            ),
            request_id=request.request_id,
            frame_id=frame.frame_id,
            sequence_id=frame.sequence_id,
            frame_index=frame.frame_index,
            captured_at=frame.captured_at,
            query=request.query,
            scene_description=runtime_value(
                "scene-description"
            ),
            entities=(
                VisualEntity(
                    entity_id=runtime_value(
                        "entity"
                    ),
                    label=runtime_value(
                        "label"
                    ),
                    confidence=0.91,
                ),
            ),
            relations=(),
            visible_text=(),
            uncertainty=(),
            provider_name=runtime_value(
                "provider"
            ),
            provider_model=runtime_value(
                "model"
            ),
            source_reference=(
                request.source_reference
            ),
            metadata={
                "generated_at": (
                    datetime.now(
                        UTC
                    ).isoformat()
                ),
            },
        )


def test_configuration_record_exposes_no_credential_value() -> None:
    configuration = direct_configuration()

    record = configuration_to_record(
        configuration
    )

    runtime = record["provider_runtime"]

    assert runtime[
        "api_key_environment_variable"
    ] == (
        configuration
        .provider_runtime
        .api_key_environment_variable
    )

    assert "api_key" not in runtime
    assert "authorization" not in runtime


def test_disabled_status(
    tmp_path: Path,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=False,
            provider="",
        ),
    )

    result = get_visual_status(
        configuration_path=configuration_path
    )

    assert result["status"] == "disabled"
    assert result["errors"] == []


def test_unknown_provider_status_is_unavailable(
    tmp_path: Path,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=True,
            provider=runtime_value(
                "unknown-provider"
            ),
        ),
    )

    result = get_visual_status(
        configuration_path=configuration_path
    )

    assert result["status"] == "unavailable"
    assert result["errors"] == []


def test_approved_provider_status_is_ready(
    tmp_path: Path,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=True,
            provider=(
                REMOTE_VISUAL_PROVIDER_TYPE
            ),
        ),
    )

    result = get_visual_status(
        configuration_path=configuration_path
    )

    assert result["status"] == "ready"

    assert result["data"][
        "runtime"
    ][
        "provider_available"
    ] is True


def test_invalid_configuration_returns_error(
    tmp_path: Path,
) -> None:
    payload = build_configuration_payload(
        enabled=True,
        provider=(
            REMOTE_VISUAL_PROVIDER_TYPE
        ),
    )

    payload[
        "visual_analysis"
    ][
        "provider_runtime"
    ][
        "request_timeout_seconds"
    ] = 0

    configuration_path = write_configuration(
        tmp_path,
        payload,
    )

    result = get_visual_status(
        configuration_path=configuration_path
    )

    assert (
        result["status"]
        == "configuration_error"
    )
    assert result["errors"]


def test_empty_query_is_rejected(
    tmp_path: Path,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=False,
            provider="",
        ),
    )

    result = analyze_image(
        image_path=write_image(tmp_path),
        query="   ",
        source_reference=None,
        configuration_path=configuration_path,
    )

    assert result["status"] == "rejected"
    assert result["data"] == {}


def test_missing_image_is_rejected(
    tmp_path: Path,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=False,
            provider="",
        ),
    )

    result = analyze_image(
        image_path=(
            tmp_path
            / "missing-image.png"
        ),
        query=runtime_value("query"),
        source_reference=None,
        configuration_path=configuration_path,
    )

    assert result["status"] == "invalid_media"
    assert result["errors"]


def test_successful_analysis_uses_factory_analyzer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=True,
            provider=(
                REMOTE_VISUAL_PROVIDER_TYPE
            ),
        ),
    )

    generated_analyzer = GeneratedAnalyzer()

    monkeypatch.setattr(
        (
            "engine.intelligence.vision."
            "application_bridge."
            "build_visual_analyzer"
        ),
        lambda configuration: (
            generated_analyzer
        ),
    )

    source_reference = runtime_value(
        "source-reference"
    )

    result = analyze_image(
        image_path=write_image(tmp_path),
        query=runtime_value("query"),
        source_reference=source_reference,
        configuration_path=configuration_path,
    )

    assert result["status"] == "success"

    observation = result["data"][
        "observation"
    ]

    assert observation is not None

    assert (
        observation["source_reference"]
        == source_reference
    )

    assert len(
        result["data"]["records"]
    ) == 1


def test_provider_configuration_failure_is_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_path = write_configuration(
        tmp_path,
        build_configuration_payload(
            enabled=True,
            provider=(
                REMOTE_VISUAL_PROVIDER_TYPE
            ),
        ),
    )

    def raise_configuration_error(
        configuration,
    ):
        del configuration

        raise VisualProviderConfigurationError(
            "Provider configuration failed."
        )

    monkeypatch.setattr(
        (
            "engine.intelligence.vision."
            "application_bridge."
            "build_visual_analyzer"
        ),
        raise_configuration_error,
    )

    result = analyze_image(
        image_path=write_image(tmp_path),
        query=runtime_value("query"),
        source_reference=None,
        configuration_path=configuration_path,
    )

    assert (
        result["status"]
        == "configuration_error"
    )

    assert result["data"].get(
        "observation"
    ) is None

    assert result["errors"] == [
        "Provider configuration failed."
    ]
