from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


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
class VisualModelResponse:
    request_id: str
    provider: str
    model_id: str
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
    duration_ms: int = 0
    validation_passed: bool = False
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_id",
            self.request_id.strip(),
        )
        object.__setattr__(
            self,
            "provider",
            self.provider.strip(),
        )
        object.__setattr__(
            self,
            "model_id",
            self.model_id.strip(),
        )
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
                text.strip()
                for text in self.visible_text
                if text.strip()
            ),
        )
        object.__setattr__(
            self,
            "uncertainty",
            tuple(
                item.strip()
                for item in self.uncertainty
                if item.strip()
            ),
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
            "metadata",
            _immutable_mapping(
                self.metadata
            ),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model_id": self.model_id,
            "scene_description": (
                self.scene_description
            ),
            "entities": [
                dict(entity)
                for entity in self.entities
            ],
            "relations": [
                dict(relation)
                for relation in self.relations
            ],
            "visible_text": list(
                self.visible_text
            ),
            "uncertainty": list(
                self.uncertainty
            ),
            "duration_ms": self.duration_ms,
            "validation_passed": (
                self.validation_passed
            ),
            "warnings": list(
                self.warnings
            ),
            "metadata": dict(
                self.metadata
            ),
        }
