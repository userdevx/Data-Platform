from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from services.visual_model.errors import (
    VisualModelRuntimeError,
)
from services.visual_model.providers.runtime_config import (
    PrivateVisualRuntimeConfiguration,
    validate_private_visual_runtime_configuration,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualRuntimeHealth,
)


def _immutable_mapping(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    return MappingProxyType(
        dict(value)
    )


def _immutable_mapping_tuple(
    values: tuple[
        Mapping[str, Any],
        ...,
    ],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        _immutable_mapping(value)
        for value in values
    )


@dataclass(frozen=True)
class PrivateVisualBackendResult:
    scene_description: str
    entities: tuple[
        Mapping[str, Any],
        ...,
    ] = ()
    relations: tuple[
        Mapping[str, Any],
        ...,
    ] = ()
    visible_text: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scene_description",
            self.scene_description.strip(),
        )
        object.__setattr__(
            self,
            "entities",
            _immutable_mapping_tuple(
                tuple(self.entities)
            ),
        )
        object.__setattr__(
            self,
            "relations",
            _immutable_mapping_tuple(
                tuple(self.relations)
            ),
        )
        object.__setattr__(
            self,
            "visible_text",
            tuple(
                value.strip()
                for value in self.visible_text
                if value.strip()
            ),
        )
        object.__setattr__(
            self,
            "uncertainty",
            tuple(
                value.strip()
                for value in self.uncertainty
                if value.strip()
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(
                value.strip()
                for value in self.warnings
                if value.strip()
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            _immutable_mapping(
                self.metadata
            ),
        )


@runtime_checkable
class PrivateVisualBackend(Protocol):
    def initialize(
        self,
        *,
        model_path: Path,
        model_id: str,
        initialization_timeout_seconds: int,
    ) -> None:
        """Initialize the backend with the configured model."""
        ...

    def is_available(self) -> bool:
        """Return whether the backend can perform inference."""
        ...

    def analyze(
        self,
        *,
        question: str,
        image_data: bytes,
        media_type: str,
        response_schema: Mapping[str, Any],
        maximum_output_tokens: int,
        inference_timeout_seconds: int,
    ) -> PrivateVisualBackendResult:
        """Perform one visual inference request."""
        ...


@dataclass
class PrivateVisualRuntime:
    configuration: PrivateVisualRuntimeConfiguration
    backend: PrivateVisualBackend
    _initialized: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        validate_private_visual_runtime_configuration(
            self.configuration
        )

        if not isinstance(
            self.backend,
            PrivateVisualBackend,
        ):
            raise TypeError(
                "backend must implement "
                "PrivateVisualBackend."
            )

    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        if not self.configuration.enabled:
            return VisualRuntimeHealth(
                available=False,
                provider=(
                    self.configuration.provider_name
                ),
                model_id=(
                    self.configuration.model_id
                ),
                message=(
                    "The private visual runtime "
                    "is disabled."
                ),
            )

        try:
            self._ensure_initialized()
        except VisualModelRuntimeError as error:
            return VisualRuntimeHealth(
                available=False,
                provider=(
                    self.configuration.provider_name
                ),
                model_id=(
                    self.configuration.model_id
                ),
                message=str(error),
            )

        try:
            available = self.backend.is_available()
        except Exception:
            return VisualRuntimeHealth(
                available=False,
                provider=(
                    self.configuration.provider_name
                ),
                model_id=(
                    self.configuration.model_id
                ),
                message=(
                    "The private visual backend "
                    "availability check failed."
                ),
            )

        return VisualRuntimeHealth(
            available=available,
            provider=(
                self.configuration.provider_name
            ),
            model_id=(
                self.configuration.model_id
            ),
            message=(
                "The private visual runtime is ready."
                if available
                else (
                    "The private visual backend "
                    "is unavailable."
                )
            ),
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        if not self.configuration.enabled:
            raise VisualModelRuntimeError(
                "The private visual runtime is disabled."
            )

        self._ensure_initialized()

        try:
            if not self.backend.is_available():
                raise VisualModelRuntimeError(
                    "The private visual backend "
                    "is unavailable."
                )
        except VisualModelRuntimeError:
            raise
        except Exception as error:
            raise VisualModelRuntimeError(
                "The private visual backend "
                "availability check failed."
            ) from error

        started_at = monotonic()

        try:
            result = self.backend.analyze(
                question=request.question,
                image_data=request.image_data,
                media_type=request.media_type,
                response_schema=(
                    request.response_schema
                ),
                maximum_output_tokens=(
                    self.configuration
                    .maximum_output_tokens
                ),
                inference_timeout_seconds=(
                    self.configuration
                    .inference_timeout_seconds
                ),
            )
        except VisualModelRuntimeError:
            raise
        except Exception as error:
            raise VisualModelRuntimeError(
                "The private visual backend "
                "failed during inference."
            ) from error

        duration_ms = max(
            0,
            int(
                (
                    monotonic()
                    - started_at
                )
                * 1000
            ),
        )

        if not isinstance(
            result,
            PrivateVisualBackendResult,
        ):
            raise VisualModelRuntimeError(
                "The private visual backend returned "
                "an invalid result type."
            )

        return VisualModelResponse(
            request_id=request.request_id,
            provider=(
                self.configuration.provider_name
            ),
            model_id=(
                self.configuration.model_id
            ),
            scene_description=(
                result.scene_description
            ),
            entities=result.entities,
            relations=result.relations,
            visible_text=result.visible_text,
            uncertainty=result.uncertainty,
            duration_ms=duration_ms,
            validation_passed=True,
            warnings=result.warnings,
            metadata={
                **dict(result.metadata),
                "source_reference": (
                    request.source_reference
                ),
                "runtime_type": (
                    self.configuration.runtime_type
                ),
            },
        )

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        model_path = Path(
            self.configuration.model_path
        ).expanduser()

        if not model_path.exists():
            raise VisualModelRuntimeError(
                "The configured visual model path "
                "does not exist."
            )

        if not model_path.is_file():
            raise VisualModelRuntimeError(
                "The configured visual model path "
                "must reference a file."
            )

        try:
            self.backend.initialize(
                model_path=model_path,
                model_id=(
                    self.configuration.model_id
                ),
                initialization_timeout_seconds=(
                    self.configuration
                    .initialization_timeout_seconds
                ),
            )
        except VisualModelRuntimeError:
            raise
        except Exception as error:
            raise VisualModelRuntimeError(
                "The private visual backend "
                "could not initialize."
            ) from error

        try:
            available = self.backend.is_available()
        except Exception as error:
            raise VisualModelRuntimeError(
                "The private visual backend "
                "availability check failed."
            ) from error

        if not available:
            raise VisualModelRuntimeError(
                "The private visual backend "
                "did not become available."
            )

        self._initialized = True
