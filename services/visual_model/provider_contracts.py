from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ProcessingLocation(StrEnum):
    LOCAL = "local"
    PRIVATE_REMOTE = "private_remote"
    CLOUD = "cloud"


class ModelStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    RETIRED = "retired"
    UNHEALTHY = "unhealthy"
    UNAUTHORIZED = "unauthorized"


def _normalize_text_set(
    values: frozenset[str] | set[str] | tuple[str, ...],
) -> frozenset[str]:
    return frozenset(
        value.strip().lower()
        for value in values
        if isinstance(value, str) and value.strip()
    )


def _immutable_mapping(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class VisualModelDescriptor:
    provider_id: str
    model_id: str
    capabilities: frozenset[str]
    processing_location: ProcessingLocation
    status: ModelStatus = ModelStatus.UNKNOWN
    supports_structured_output: bool = False
    enabled: bool = True
    priority: int = 100
    license_identifier: str = ""
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        provider_id = self.provider_id.strip()
        model_id = self.model_id.strip()

        if not provider_id:
            raise ValueError(
                "provider_id is required."
            )

        if not model_id:
            raise ValueError(
                "model_id is required."
            )

        if self.priority < 0:
            raise ValueError(
                "priority must not be negative."
            )

        object.__setattr__(
            self,
            "provider_id",
            provider_id,
        )
        object.__setattr__(
            self,
            "model_id",
            model_id,
        )
        object.__setattr__(
            self,
            "capabilities",
            _normalize_text_set(
                self.capabilities
            ),
        )
        object.__setattr__(
            self,
            "license_identifier",
            self.license_identifier.strip(),
        )
        object.__setattr__(
            self,
            "metadata",
            _immutable_mapping(
                self.metadata
            ),
        )


@dataclass(frozen=True)
class VisualCapabilityRequest:
    required_capabilities: frozenset[str]
    preferred_processing_location: (
        ProcessingLocation | None
    ) = ProcessingLocation.LOCAL
    allow_cloud_fallback: bool = False
    require_structured_output: bool = True
    maximum_attempts: int = 2

    def __post_init__(self) -> None:
        capabilities = _normalize_text_set(
            self.required_capabilities
        )

        if not capabilities:
            raise ValueError(
                "At least one required capability "
                "must be provided."
            )

        if self.maximum_attempts < 1:
            raise ValueError(
                "maximum_attempts must be positive."
            )

        object.__setattr__(
            self,
            "required_capabilities",
            capabilities,
        )


@dataclass(frozen=True)
class VisualProviderRequest:
    request_id: str
    question: str
    image_data: bytes
    media_type: str
    required_capabilities: frozenset[str]
    response_schema: Mapping[str, Any] = field(
        default_factory=dict
    )
    maximum_output_tokens: int = 512

    def __post_init__(self) -> None:
        request_id = self.request_id.strip()
        question = self.question.strip()
        media_type = self.media_type.strip().lower()

        if not request_id:
            raise ValueError(
                "request_id is required."
            )

        if not question:
            raise ValueError(
                "question is required."
            )

        if not self.image_data:
            raise ValueError(
                "image_data is required."
            )

        if not media_type.startswith("image/"):
            raise ValueError(
                "media_type must be an image type."
            )

        if self.maximum_output_tokens < 1:
            raise ValueError(
                "maximum_output_tokens must be positive."
            )

        object.__setattr__(
            self,
            "request_id",
            request_id,
        )
        object.__setattr__(
            self,
            "question",
            question,
        )
        object.__setattr__(
            self,
            "media_type",
            media_type,
        )
        object.__setattr__(
            self,
            "required_capabilities",
            _normalize_text_set(
                self.required_capabilities
            ),
        )
        object.__setattr__(
            self,
            "response_schema",
            _immutable_mapping(
                self.response_schema
            ),
        )


@dataclass(frozen=True)
class VisualProviderResult:
    provider_id: str
    model_id: str
    result: Mapping[str, Any]
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError(
                "provider_id is required."
            )

        if not self.model_id.strip():
            raise ValueError(
                "model_id is required."
            )

        object.__setattr__(
            self,
            "provider_id",
            self.provider_id.strip(),
        )
        object.__setattr__(
            self,
            "model_id",
            self.model_id.strip(),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(
                warning.strip()
                for warning in self.warnings
                if warning.strip()
            ),
        )
        object.__setattr__(
            self,
            "result",
            _immutable_mapping(
                self.result
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            _immutable_mapping(
                self.metadata
            ),
        )
