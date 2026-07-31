from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisualModelResponse:
    request_id: str
    provider: str
    model_id: str
    scene_description: str
    entities: tuple[
        dict[str, Any],
        ...,
    ] = ()
    relations: tuple[
        dict[str, Any],
        ...,
    ] = ()
    visible_text: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    duration_ms: int = 0
    validation_passed: bool = False
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(
        default_factory=dict
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
