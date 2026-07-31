from __future__ import annotations

from uuid import uuid4

from engine.intelligence.vision.config import (
    ProviderRuntimeConfiguration,
    SamplingConfiguration,
    StorageConfiguration,
    ValidationConfiguration,
    VisualConfiguration,
)
from engine.intelligence.vision.provider_factory import (
    REMOTE_VISUAL_PROVIDER_TYPE,
    build_visual_analyzer,
    build_visual_analyzer_registry,
)
from engine.intelligence.vision.providers.cloud_mapping_adapter import (
    CloudVisualMappingAdapter,
)
from engine.intelligence.vision.providers.unavailable import (
    UnavailableVisualAnalyzer,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_configuration(
    *,
    enabled: bool,
    provider: str,
) -> VisualConfiguration:
    return VisualConfiguration(
        enabled=enabled,
        provider=provider,
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
                        "api-key-environment-variable"
                    )
                    if enabled
                    else ""
                ),
                request_timeout_seconds=30,
                maximum_output_tokens=1024,
            )
        ),
    )


def test_disabled_configuration_returns_unavailable() -> None:
    analyzer = build_visual_analyzer(
        build_configuration(
            enabled=False,
            provider="",
        )
    )

    assert isinstance(
        analyzer,
        UnavailableVisualAnalyzer,
    )


def test_unknown_provider_returns_unavailable() -> None:
    analyzer = build_visual_analyzer(
        build_configuration(
            enabled=True,
            provider=runtime_value(
                "unknown-provider"
            ),
        )
    )

    assert isinstance(
        analyzer,
        UnavailableVisualAnalyzer,
    )


def test_remote_provider_builds_mapping_adapter() -> None:
    analyzer = build_visual_analyzer(
        build_configuration(
            enabled=True,
            provider=(
                REMOTE_VISUAL_PROVIDER_TYPE
            ),
        )
    )

    assert isinstance(
        analyzer,
        CloudVisualMappingAdapter,
    )


def test_registry_contains_approved_provider() -> None:
    registry = build_visual_analyzer_registry(
        build_configuration(
            enabled=True,
            provider=(
                REMOTE_VISUAL_PROVIDER_TYPE
            ),
        )
    )

    assert registry.registered_names() == (
        REMOTE_VISUAL_PROVIDER_TYPE,
    )


def test_disabled_registry_is_empty() -> None:
    registry = build_visual_analyzer_registry(
        build_configuration(
            enabled=False,
            provider="",
        )
    )

    assert registry.registered_names() == ()


def test_unknown_provider_registry_is_empty() -> None:
    registry = build_visual_analyzer_registry(
        build_configuration(
            enabled=True,
            provider=runtime_value(
                "unknown-provider"
            ),
        )
    )

    assert registry.registered_names() == ()
