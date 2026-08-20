from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse

from services.visual_model.provider_contracts import (
    ModelStatus,
    ProcessingLocation,
    VisualModelDescriptor,
)
from services.visual_model.provider_errors import (
    VisualProviderConfigurationError,
)


@dataclass(frozen=True)
class ProviderSelectionPolicy:
    prefer_local: bool = True
    allow_cloud_fallback: bool = True
    require_runtime_health_check: bool = True
    maximum_attempts: int = 2

    def __post_init__(self) -> None:
        if self.maximum_attempts < 1:
            raise VisualProviderConfigurationError(
                "maximum_attempts must be positive."
            )


@dataclass(frozen=True)
class VisualProviderConfiguration:
    provider_id: str
    adapter_type: str
    processing_location: ProcessingLocation
    enabled: bool
    endpoint: str
    credential_reference: str = ""
    discovery_path: str = ""
    health_path: str = ""
    analyze_path: str = ""
    timeout_seconds: int = 30
    models: tuple[VisualModelDescriptor, ...] = ()
    headers: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        provider_id = self.provider_id.strip()
        adapter_type = self.adapter_type.strip().lower()
        endpoint = self.endpoint.strip().rstrip("/")

        if not provider_id:
            raise VisualProviderConfigurationError(
                "provider_id is required."
            )

        if not adapter_type:
            raise VisualProviderConfigurationError(
                "adapter_type is required."
            )

        if self.timeout_seconds < 1:
            raise VisualProviderConfigurationError(
                "timeout_seconds must be positive."
            )

        if self.enabled:
            _validate_endpoint(
                endpoint=endpoint,
                processing_location=(
                    self.processing_location
                ),
            )

        for model in self.models:
            if model.provider_id != provider_id:
                raise VisualProviderConfigurationError(
                    "Every configured model must use "
                    "its parent provider_id."
                )

        object.__setattr__(
            self,
            "provider_id",
            provider_id,
        )
        object.__setattr__(
            self,
            "adapter_type",
            adapter_type,
        )
        object.__setattr__(
            self,
            "endpoint",
            endpoint,
        )
        object.__setattr__(
            self,
            "credential_reference",
            self.credential_reference.strip(),
        )
        object.__setattr__(
            self,
            "discovery_path",
            _normalize_path(
                self.discovery_path
            ),
        )
        object.__setattr__(
            self,
            "health_path",
            _normalize_path(
                self.health_path
            ),
        )
        object.__setattr__(
            self,
            "analyze_path",
            _normalize_path(
                self.analyze_path
            ),
        )
        object.__setattr__(
            self,
            "headers",
            MappingProxyType(
                dict(self.headers)
            ),
        )


@dataclass(frozen=True)
class VisualModelRegistryConfiguration:
    enabled: bool
    selection_policy: ProviderSelectionPolicy
    providers: tuple[
        VisualProviderConfiguration,
        ...
    ]

    def __post_init__(self) -> None:
        provider_ids = [
            provider.provider_id
            for provider in self.providers
        ]

        if len(provider_ids) != len(
            set(provider_ids)
        ):
            raise VisualProviderConfigurationError(
                "Provider identifiers must be unique."
            )


def _normalize_path(
    value: str,
) -> str:
    value = value.strip()

    if not value:
        return ""

    if not value.startswith("/"):
        return f"/{value}"

    return value


def _validate_endpoint(
    *,
    endpoint: str,
    processing_location: ProcessingLocation,
) -> None:
    if not endpoint:
        raise VisualProviderConfigurationError(
            "An enabled provider requires endpoint."
        )

    parsed = urlparse(endpoint)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise VisualProviderConfigurationError(
            "Provider endpoint must use HTTP or HTTPS."
        )

    if not parsed.hostname:
        raise VisualProviderConfigurationError(
            "Provider endpoint requires a hostname."
        )

    if (
        processing_location
        is ProcessingLocation.CLOUD
        and parsed.scheme != "https"
    ):
        raise VisualProviderConfigurationError(
            "Cloud providers must use HTTPS."
        )


def _require_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VisualProviderConfigurationError(
            f"{field_name} must be an object."
        )

    return value


def _require_list(
    value: Any,
    *,
    field_name: str,
) -> list[Any]:
    if not isinstance(value, list):
        raise VisualProviderConfigurationError(
            f"{field_name} must be an array."
        )

    return value


def _require_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise VisualProviderConfigurationError(
            f"{field_name} must be text."
        )

    return value


def _require_boolean(
    value: Any,
    *,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise VisualProviderConfigurationError(
            f"{field_name} must be a boolean."
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
        raise VisualProviderConfigurationError(
            f"{field_name} must be an integer."
        )

    return value


def _parse_capabilities(
    value: Any,
    *,
    field_name: str,
) -> frozenset[str]:
    items = _require_list(
        value,
        field_name=field_name,
    )

    capabilities: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise VisualProviderConfigurationError(
                f"{field_name}[{index}] "
                "must be text."
            )

        normalized = item.strip().lower()

        if normalized:
            capabilities.add(normalized)

    return frozenset(capabilities)


def _parse_headers(
    value: Any,
) -> dict[str, str]:
    mapping = _require_mapping(
        value,
        field_name="headers",
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
            raise VisualProviderConfigurationError(
                "Header names and values must be text."
            )

        result[key] = item

    return result


def _parse_model(
    *,
    provider_id: str,
    processing_location: ProcessingLocation,
    payload: dict[str, Any],
) -> VisualModelDescriptor:
    status_text = _require_text(
        payload.get(
            "status",
            ModelStatus.UNKNOWN.value,
        ),
        field_name="model.status",
    )

    try:
        status = ModelStatus(
            status_text.strip().lower()
        )
    except ValueError as error:
        raise VisualProviderConfigurationError(
            f"Unsupported model status: {status_text}"
        ) from error

    return VisualModelDescriptor(
        provider_id=provider_id,
        model_id=_require_text(
            payload.get("model_id", ""),
            field_name="model.model_id",
        ),
        capabilities=_parse_capabilities(
            payload.get("capabilities", []),
            field_name="model.capabilities",
        ),
        processing_location=processing_location,
        status=status,
        supports_structured_output=(
            _require_boolean(
                payload.get(
                    "supports_structured_output",
                    False,
                ),
                field_name=(
                    "model.supports_structured_output"
                ),
            )
        ),
        enabled=_require_boolean(
            payload.get("enabled", True),
            field_name="model.enabled",
        ),
        priority=_require_integer(
            payload.get("priority", 100),
            field_name="model.priority",
        ),
        license_identifier=_require_text(
            payload.get(
                "license_identifier",
                "",
            ),
            field_name="model.license_identifier",
        ),
        metadata=_require_mapping(
            payload.get("metadata", {}),
            field_name="model.metadata",
        ),
    )


def _parse_provider(
    payload: dict[str, Any],
) -> VisualProviderConfiguration:
    provider_id = _require_text(
        payload.get("provider_id", ""),
        field_name="provider.provider_id",
    ).strip()

    location_text = _require_text(
        payload.get(
            "processing_location",
            "",
        ),
        field_name=(
            "provider.processing_location"
        ),
    )

    try:
        processing_location = ProcessingLocation(
            location_text.strip().lower()
        )
    except ValueError as error:
        raise VisualProviderConfigurationError(
            "Unsupported processing location: "
            f"{location_text}"
        ) from error

    models = tuple(
        _parse_model(
            provider_id=provider_id,
            processing_location=(
                processing_location
            ),
            payload=_require_mapping(
                item,
                field_name="provider.models[]",
            ),
        )
        for item in _require_list(
            payload.get("models", []),
            field_name="provider.models",
        )
    )

    return VisualProviderConfiguration(
        provider_id=provider_id,
        adapter_type=_require_text(
            payload.get("adapter_type", ""),
            field_name="provider.adapter_type",
        ),
        processing_location=processing_location,
        enabled=_require_boolean(
            payload.get("enabled", False),
            field_name="provider.enabled",
        ),
        endpoint=_require_text(
            payload.get("endpoint", ""),
            field_name="provider.endpoint",
        ),
        credential_reference=_require_text(
            payload.get(
                "credential_reference",
                "",
            ),
            field_name=(
                "provider.credential_reference"
            ),
        ),
        discovery_path=_require_text(
            payload.get("discovery_path", ""),
            field_name="provider.discovery_path",
        ),
        health_path=_require_text(
            payload.get("health_path", ""),
            field_name="provider.health_path",
        ),
        analyze_path=_require_text(
            payload.get("analyze_path", ""),
            field_name="provider.analyze_path",
        ),
        timeout_seconds=_require_integer(
            payload.get("timeout_seconds", 30),
            field_name="provider.timeout_seconds",
        ),
        models=models,
        headers=_parse_headers(
            payload.get("headers", {})
        ),
    )


def load_visual_model_registry_configuration(
    path: Path,
) -> VisualModelRegistryConfiguration:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except OSError as error:
        raise VisualProviderConfigurationError(
            "The visual model registry "
            "configuration could not be read."
        ) from error
    except json.JSONDecodeError as error:
        raise VisualProviderConfigurationError(
            "The visual model registry "
            "configuration contains invalid JSON."
        ) from error

    root = _require_mapping(
        payload.get("visual_model_registry"),
        field_name="visual_model_registry",
    )

    policy_payload = _require_mapping(
        root.get("selection_policy", {}),
        field_name=(
            "visual_model_registry.selection_policy"
        ),
    )

    policy = ProviderSelectionPolicy(
        prefer_local=_require_boolean(
            policy_payload.get(
                "prefer_local",
                True,
            ),
            field_name=(
                "selection_policy.prefer_local"
            ),
        ),
        allow_cloud_fallback=_require_boolean(
            policy_payload.get(
                "allow_cloud_fallback",
                True,
            ),
            field_name=(
                "selection_policy."
                "allow_cloud_fallback"
            ),
        ),
        require_runtime_health_check=(
            _require_boolean(
                policy_payload.get(
                    "require_runtime_health_check",
                    True,
                ),
                field_name=(
                    "selection_policy."
                    "require_runtime_health_check"
                ),
            )
        ),
        maximum_attempts=_require_integer(
            policy_payload.get(
                "maximum_attempts",
                2,
            ),
            field_name=(
                "selection_policy.maximum_attempts"
            ),
        ),
    )

    providers = tuple(
        _parse_provider(
            _require_mapping(
                item,
                field_name="providers[]",
            )
        )
        for item in _require_list(
            root.get("providers", []),
            field_name=(
                "visual_model_registry.providers"
            ),
        )
    )

    return VisualModelRegistryConfiguration(
        enabled=_require_boolean(
            root.get("enabled", False),
            field_name=(
                "visual_model_registry.enabled"
            ),
        ),
        selection_policy=policy,
        providers=providers,
    )
