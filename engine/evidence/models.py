from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(kw_only=True)
class ProvenanceLink:
    from_id: UUID
    from_type: str
    relation: str = "derived_from"


@runtime_checkable
class Record(Protocol):
    id: UUID
    created_at: datetime
    provenance: list[ProvenanceLink]


@dataclass(kw_only=True)
class Entity:
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    provenance: list[ProvenanceLink] = field(
        default_factory=list
    )

    def derive(
        self,
        relation: str = "derived_from",
    ) -> ProvenanceLink:
        return ProvenanceLink(
            from_id=self.id,
            from_type=type(self).__name__,
            relation=relation,
        )


@dataclass(frozen=True, kw_only=True)
class ImmutableEntity:
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    provenance: list[ProvenanceLink] = field(
        default_factory=list
    )

    def derive(
        self,
        relation: str = "derived_from",
    ) -> ProvenanceLink:
        return ProvenanceLink(
            from_id=self.id,
            from_type=type(self).__name__,
            relation=relation,
        )


@dataclass(kw_only=True)
class RawInformation(Entity):
    source_id: str
    source_type: str
    raw_text: str
    url: str | None = None
    retrieved_at: datetime = field(
        default_factory=_now
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class NormalizedInformation(Entity):
    raw_information_id: UUID
    normalized_text: str
    language: str | None = None


@dataclass(kw_only=True)
class Analysis(Entity):
    information_id: UUID
    topics: list[str] = field(
        default_factory=list
    )
    sentiment: float | None = None
    confidence: float = 0.0

    def __post_init__(
        self,
    ) -> None:
        if not (
            0.0
            <= self.confidence
            <= 1.0
        ):
            raise ValueError(
                "confidence must be in [0,1], "
                f"got {self.confidence}"
            )

        if (
            self.sentiment is not None
            and not (
                -1.0
                <= self.sentiment
                <= 1.0
            )
        ):
            raise ValueError(
                "sentiment must be in [-1,1], "
                f"got {self.sentiment}"
            )


@dataclass(kw_only=True)
class ValidatedTrend(Entity):
    topic: str
    description: str
    supporting_analysis_ids: list[UUID]
    source_diversity_score: float
    confidence: float


@dataclass(kw_only=True)
class ProductRequirement(Entity):
    trend_id: UUID
    title: str
    description: str
    priority: str = "normal"
    status: str = "proposed"


@dataclass(kw_only=True)
class ApplicationRequest(Entity):
    request_text: str
    requested_by: str | None = None


@dataclass(kw_only=True)
class UserRequirement(Entity):
    request_id: UUID
    requirement_type: str
    answer: str
    status: str = "proposed"


class EngineeringPlanStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(kw_only=True)
class ApplicationRecord(Entity):
    name: str
    repo_path: str
    requirement_ids: list[UUID] = field(
        default_factory=list
    )
    status: str = "active"


@dataclass(kw_only=True)
class EngineeringPlan(Entity):
    application_id: UUID
    requirement_ids: list[UUID]
    steps: list[str]
    status: EngineeringPlanStatus = (
        EngineeringPlanStatus.PROPOSED
    )


@dataclass(frozen=True, kw_only=True)
class EngineeringCheckpoint(ImmutableEntity):
    application_id: UUID
    plan_id: UUID
    checkpoint_type: str
    revision: str
    recoverable: bool


@dataclass(kw_only=True)
class BuildRecord(Entity):
    application_id: UUID
    plan_id: UUID
    checkpoint_id: UUID
    status: str = "pending"
    log: str = ""


@dataclass(kw_only=True)
class TestRecord(Entity):
    build_id: UUID
    passed: bool
    details: str = ""


@dataclass(kw_only=True)
class ReleaseRecord(Entity):
    application_id: UUID
    build_id: UUID
    version: str
    outcome_type: str
    status: str = "released"


@dataclass(kw_only=True)
class RuntimeMetric(Entity):
    application_id: UUID
    metric_name: str
    value: Any
    observed_at: datetime = field(
        default_factory=_now
    )


@dataclass(kw_only=True)
class MaintenanceEvent(Entity):
    application_id: UUID
    trigger: str
    recommendation: str
    resulting_plan_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class FileChange:
    path: str
    action: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class CodeChange(ImmutableEntity):
    application_id: UUID
    plan_id: UUID
    checkpoint_id: UUID
    files: tuple[FileChange, ...]
