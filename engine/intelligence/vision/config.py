from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SamplingConfiguration:
    minimum_interval_ms: int
    maximum_interval_ms: int
    analyze_on_change: bool
    maximum_pending_frames: int


@dataclass(frozen=True)
class ValidationConfiguration:
    minimum_entity_confidence: float
    minimum_relation_confidence: float
    minimum_temporal_frames: int


@dataclass(frozen=True)
class StorageConfiguration:
    store_raw_frames: bool
    store_provider_responses: bool
    store_validated_observations: bool


@dataclass(frozen=True)
class ProviderRuntimeConfiguration:
    endpoint_url: str = ""
    api_key_environment_variable: str = ""
    request_timeout_seconds: int = 30
    maximum_output_tokens: int = 1024


@dataclass(frozen=True)
class VisualConfiguration:
    enabled: bool
    provider: str
    model: str
    maximum_media_size_bytes: int
    sampling: SamplingConfiguration
    validation: ValidationConfiguration
    storage: StorageConfiguration
    provider_runtime: ProviderRuntimeConfiguration = field(
        default_factory=ProviderRuntimeConfiguration
    )


def _mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{field_name} must be an object."
        )

    return value


def _optional_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if value is None:
        return {}

    return _mapping(
        value,
        field_name=field_name,
    )


def _bounded_confidence(
    value: Any,
    *,
    field_name: str,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be numeric."
        ) from error

    if not 0.0 <= number <= 1.0:
        raise ValueError(
            f"{field_name} must be between 0 and 1."
        )

    return number


def load_visual_configuration(
    path: Path,
) -> VisualConfiguration:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    root = _mapping(
        payload.get("visual_analysis"),
        field_name="visual_analysis",
    )

    sampling = _mapping(
        root.get("sampling"),
        field_name="visual_analysis.sampling",
    )

    validation = _mapping(
        root.get("validation"),
        field_name="visual_analysis.validation",
    )

    storage = _mapping(
        root.get("storage"),
        field_name="visual_analysis.storage",
    )

    provider_runtime = _optional_mapping(
        root.get("provider_runtime"),
        field_name=(
            "visual_analysis.provider_runtime"
        ),
    )

    configuration = VisualConfiguration(
        enabled=bool(
            root.get("enabled", False)
        ),
        provider=str(
            root.get("provider", "")
        ).strip(),
        model=str(
            root.get("model", "")
        ).strip(),
        maximum_media_size_bytes=int(
            root.get(
                "maximum_media_size_bytes",
                0,
            )
        ),
        sampling=SamplingConfiguration(
            minimum_interval_ms=int(
                sampling.get(
                    "minimum_interval_ms",
                    0,
                )
            ),
            maximum_interval_ms=int(
                sampling.get(
                    "maximum_interval_ms",
                    0,
                )
            ),
            analyze_on_change=bool(
                sampling.get(
                    "analyze_on_change",
                    True,
                )
            ),
            maximum_pending_frames=int(
                sampling.get(
                    "maximum_pending_frames",
                    0,
                )
            ),
        ),
        validation=ValidationConfiguration(
            minimum_entity_confidence=(
                _bounded_confidence(
                    validation.get(
                        "minimum_entity_confidence",
                        0.0,
                    ),
                    field_name=(
                        "minimum_entity_confidence"
                    ),
                )
            ),
            minimum_relation_confidence=(
                _bounded_confidence(
                    validation.get(
                        "minimum_relation_confidence",
                        0.0,
                    ),
                    field_name=(
                        "minimum_relation_confidence"
                    ),
                )
            ),
            minimum_temporal_frames=int(
                validation.get(
                    "minimum_temporal_frames",
                    2,
                )
            ),
        ),
        storage=StorageConfiguration(
            store_raw_frames=bool(
                storage.get(
                    "store_raw_frames",
                    False,
                )
            ),
            store_provider_responses=bool(
                storage.get(
                    "store_provider_responses",
                    False,
                )
            ),
            store_validated_observations=bool(
                storage.get(
                    "store_validated_observations",
                    True,
                )
            ),
        ),
        provider_runtime=(
            ProviderRuntimeConfiguration(
                endpoint_url=str(
                    provider_runtime.get(
                        "endpoint_url",
                        "",
                    )
                ).strip(),
                api_key_environment_variable=str(
                    provider_runtime.get(
                        "api_key_environment_variable",
                        "",
                    )
                ).strip(),
                request_timeout_seconds=int(
                    provider_runtime.get(
                        "request_timeout_seconds",
                        30,
                    )
                ),
                maximum_output_tokens=int(
                    provider_runtime.get(
                        "maximum_output_tokens",
                        1024,
                    )
                ),
            )
        ),
    )

    validate_visual_configuration(
        configuration
    )

    return configuration


def validate_visual_configuration(
    configuration: VisualConfiguration,
) -> None:
    if configuration.maximum_media_size_bytes < 1:
        raise ValueError(
            "maximum_media_size_bytes must be positive."
        )

    if (
        configuration.sampling.minimum_interval_ms
        < 1
    ):
        raise ValueError(
            "minimum_interval_ms must be positive."
        )

    if (
        configuration.sampling.maximum_interval_ms
        < configuration.sampling.minimum_interval_ms
    ):
        raise ValueError(
            "maximum_interval_ms cannot be less than "
            "minimum_interval_ms."
        )

    if (
        configuration.sampling.maximum_pending_frames
        < 1
    ):
        raise ValueError(
            "maximum_pending_frames must be positive."
        )

    if (
        configuration.validation.minimum_temporal_frames
        < 2
    ):
        raise ValueError(
            "minimum_temporal_frames must be at least 2."
        )

    runtime = configuration.provider_runtime

    if runtime.request_timeout_seconds < 1:
        raise ValueError(
            "request_timeout_seconds must be positive."
        )

    if runtime.maximum_output_tokens < 1:
        raise ValueError(
            "maximum_output_tokens must be positive."
        )

    if not configuration.enabled:
        return

    if not configuration.provider:
        raise ValueError(
            "An enabled visual runtime requires a provider."
        )

    if not configuration.model:
        raise ValueError(
            "An enabled visual runtime requires a model."
        )

    if not runtime.endpoint_url:
        raise ValueError(
            "An enabled visual runtime requires "
            "a provider endpoint URL."
        )

    if not runtime.api_key_environment_variable:
        raise ValueError(
            "An enabled visual runtime requires "
            "an API key environment-variable name."
        )
