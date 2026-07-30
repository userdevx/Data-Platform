from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisualAnalysisRequest:
    request_id: str
    query: str
    media_source_id: str
    media_mode: str
    created_at: str
    requested_outputs: tuple[str, ...] = ()
    sequence_id: str | None = None
    source_reference: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MediaFrame:
    frame_id: str
    source_id: str
    sequence_id: str
    frame_index: int
    captured_at: str
    media_location: str
    media_type: str
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualEntity:
    entity_id: str
    label: str
    confidence: float
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualRelation:
    subject_id: str
    predicate: str
    object_id: str | None
    confidence: float
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualObservation:
    observation_id: str
    request_id: str
    frame_id: str
    sequence_id: str
    frame_index: int
    captured_at: str
    query: str
    scene_description: str
    entities: tuple[VisualEntity, ...]
    relations: tuple[VisualRelation, ...]
    visible_text: tuple[str, ...]
    uncertainty: tuple[str, ...]
    provider_name: str
    provider_model: str
    source_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": "visual_observation",
            "observation_id": self.observation_id,
            "request_id": self.request_id,
            "frame_id": self.frame_id,
            "sequence_id": self.sequence_id,
            "frame_index": self.frame_index,
            "captured_at": self.captured_at,
            "query": self.query,
            "scene_description": self.scene_description,
            "entities": [
                entity.to_record()
                for entity in self.entities
            ],
            "relations": [
                relation.to_record()
                for relation in self.relations
            ],
            "visible_text": list(self.visible_text),
            "uncertainty": list(self.uncertainty),
            "provider": {
                "name": self.provider_name,
                "model": self.provider_model,
            },
            "source_reference": self.source_reference,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class EntityAssociation:
    association_id: str
    sequence_id: str
    previous_observation_id: str
    current_observation_id: str
    previous_entity_id: str
    current_entity_id: str
    confidence: float
    evidence: tuple[str, ...]

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalObservation:
    temporal_observation_id: str
    request_id: str
    sequence_id: str
    query: str
    supporting_observation_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    description: str
    confidence: float
    uncertainty: tuple[str, ...]
    started_at: str
    ended_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualStateRecord:
    state_id: str
    request_id: str
    sequence_id: str
    query: str
    description: str
    status: str
    first_observed_at: str
    last_observed_at: str
    observation_ids: tuple[str, ...]
    confidence: float
    uncertainty: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualRuntimeResult:
    status: str
    answer: str
    observation: VisualObservation | None = None
    temporal_observation: TemporalObservation | None = None
    errors: tuple[str, ...] = ()
    records: tuple[dict[str, Any], ...] = ()
