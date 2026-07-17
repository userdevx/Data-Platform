from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    clean_value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(clean_value)


class MemoryKind(str, Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETED = "deleted"
    EXPIRED = "expired"


class MemoryOperation(str, Enum):
    ASSERT = "assert"
    RETRACT = "retract"
    REPLACE = "replace"
    CONFIRM = "confirm"
    IGNORE = "ignore"


@dataclass(slots=True)
class MemoryCandidate:
    user_id: str
    intelligence_id: str
    kind: MemoryKind
    namespace: str
    subject: str
    predicate: str
    value: Any
    canonical_text: str
    confidence: float
    importance: float
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    source_text: str = ""
    explicit_request: bool = False
    operation: MemoryOperation = MemoryOperation.ASSERT
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MemoryRecord:
    memory_id: UUID = field(default_factory=uuid4)
    user_id: str = ""
    intelligence_id: str = ""
    kind: MemoryKind = MemoryKind.SEMANTIC
    namespace: str = "default"
    subject: str = ""
    predicate: str = ""
    value: Any = None
    canonical_text: str = ""
    confidence: float = 0.0
    importance: float = 0.0
    sensitivity: str = "normal"
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    source_text_hash: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_accessed_at: datetime | None = None
    access_count: int = 0
    status: MemoryStatus = MemoryStatus.ACTIVE
    supersedes_memory_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_current(self, now: datetime | None = None) -> bool:
        current_time = now or utc_now()

        if self.status is not MemoryStatus.ACTIVE:
            return False

        if self.valid_from and self.valid_from > current_time:
            return False

        if self.valid_until and self.valid_until <= current_time:
            return False

        return True

    def to_engine_record(self) -> dict[str, Any]:
        return {
            "record_id": str(self.memory_id),
            "source": "intelligence",
            "category": "memory",
            "sensor_type": f"{self.kind.value}_memory",
            "value": {
                "subject": self.subject,
                "predicate": self.predicate,
                "value": self.value,
                "canonical_text": self.canonical_text,
            },
            "unit": None,
            "timestamp": self.created_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": {
                "user_id": self.user_id,
                "intelligence_id": self.intelligence_id,
                "namespace": self.namespace,
                "kind": self.kind.value,
                "confidence": self.confidence,
                "importance": self.importance,
                "sensitivity": self.sensitivity,
                "source_conversation_id": self.source_conversation_id,
                "source_message_id": self.source_message_id,
                "source_text_hash": self.source_text_hash,
                "valid_from": self.valid_from.isoformat() if self.valid_from else None,
                "valid_until": self.valid_until.isoformat() if self.valid_until else None,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
                "last_accessed_at": (
                    self.last_accessed_at.isoformat()
                    if self.last_accessed_at
                    else None
                ),
                "access_count": self.access_count,
                "status": self.status.value,
                "supersedes_memory_id": (
                    str(self.supersedes_memory_id)
                    if self.supersedes_memory_id
                    else None
                ),
                **self.metadata,
            },
        }

    @classmethod
    def from_engine_record(cls, record: dict[str, Any]) -> MemoryRecord:
        value = record.get("value", {})
        metadata = record.get("metadata", {})

        return cls(
            memory_id=UUID(record["record_id"]),
            user_id=metadata["user_id"],
            intelligence_id=metadata["intelligence_id"],
            kind=MemoryKind(metadata["kind"]),
            namespace=metadata.get("namespace", "default"),
            subject=value["subject"],
            predicate=value["predicate"],
            value=value.get("value"),
            canonical_text=value["canonical_text"],
            confidence=float(metadata.get("confidence", 0.0)),
            importance=float(metadata.get("importance", 0.0)),
            sensitivity=metadata.get("sensitivity", "normal"),
            source_conversation_id=metadata.get("source_conversation_id"),
            source_message_id=metadata.get("source_message_id"),
            source_text_hash=metadata.get("source_text_hash"),
            valid_from=parse_datetime(metadata.get("valid_from")),
            valid_until=parse_datetime(metadata.get("valid_until")),
            created_at=parse_datetime(metadata.get("created_at")) or utc_now(),
            updated_at=parse_datetime(metadata.get("updated_at")) or utc_now(),
            last_accessed_at=parse_datetime(metadata.get("last_accessed_at")),
            access_count=int(metadata.get("access_count", 0)),
            status=MemoryStatus(metadata.get("status", MemoryStatus.ACTIVE.value)),
            supersedes_memory_id=(
                UUID(metadata["supersedes_memory_id"])
                if metadata.get("supersedes_memory_id")
                else None
            ),
            metadata={
                key: item
                for key, item in metadata.items()
                if key
                not in {
                    "user_id",
                    "intelligence_id",
                    "namespace",
                    "kind",
                    "confidence",
                    "importance",
                    "sensitivity",
                    "source_conversation_id",
                    "source_message_id",
                    "source_text_hash",
                    "valid_from",
                    "valid_until",
                    "created_at",
                    "updated_at",
                    "last_accessed_at",
                    "access_count",
                    "status",
                    "supersedes_memory_id",
                }
            },
        )


@dataclass(slots=True)
class ValidationResult:
    should_store: bool
    reason: str | None = None
    sensitivity: str = "normal"

    @classmethod
    def accept(cls, sensitivity: str = "normal") -> ValidationResult:
        return cls(should_store=True, sensitivity=sensitivity)

    @classmethod
    def reject(cls, reason: str) -> ValidationResult:
        return cls(should_store=False, reason=reason)
