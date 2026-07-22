from __future__ import annotations

from typing import Any

from engine.memory.context_builder import MemoryContextBuilder
from engine.memory.models import (
    MemoryCandidate,
    MemoryKind,
    MemoryStatus,
)
from engine.memory.repository import MemoryRepository
from engine.memory.retrieval import MemoryRetriever
from engine.memory.service import MemoryService
from engine.memory.validation import MemoryValidator


class FakeDataEngine:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.rebuilt_indexes: list[str] = []

    def store(self, record: dict[str, Any]) -> None:
        self.records[record["record_id"]] = record

    def replace(
        self,
        record_id: str,
        record: dict[str, Any],
    ) -> None:
        self.records[record_id] = record

    def query(
        self,
        *,
        source: str | None = None,
        category: str | None = None,
        sensor_type: str | None = None,
        metadata_filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        records = list(self.records.values())

        if source is not None:
            records = [
                record
                for record in records
                if record.get("source") == source
            ]

        if category is not None:
            records = [
                record
                for record in records
                if record.get("category") == category
            ]

        if sensor_type is not None:
            records = [
                record
                for record in records
                if record.get("sensor_type") == sensor_type
            ]

        for key, expected in (metadata_filters or {}).items():
            records = [
                record
                for record in records
                if record.get("metadata", {}).get(key) == expected
            ]

        if limit is not None:
            records = records[:limit]

        return records

    def get(
        self,
        record_id: str,
    ) -> dict[str, Any] | None:
        return self.records.get(record_id)

    def rebuild_index(
        self,
        index_name: str,
    ) -> None:
        self.rebuilt_indexes.append(index_name)


def build_service() -> tuple[
    FakeDataEngine,
    MemoryRepository,
    MemoryService,
]:
    data_engine = FakeDataEngine()
    repository = MemoryRepository(data_engine)

    service = MemoryService(
        repository=repository,
        validator=MemoryValidator(),
        retriever=MemoryRetriever(),
        context_builder=MemoryContextBuilder(),
    )

    return data_engine, repository, service


def language_candidate(
    value: str,
) -> MemoryCandidate:
    return MemoryCandidate(
        user_id="local_user",
        intelligence_id="default",
        kind=MemoryKind.PROCEDURAL,
        namespace="implementation_preferences",
        subject="user",
        predicate="preferred_implementation_language",
        value=value,
        canonical_text=(
            f"The user prefers {value} for implementation examples."
        ),
        confidence=0.98,
        importance=0.90,
        source_text=(
            f"Remember that implementation examples should use {value}."
        ),
        explicit_request=True,
    )


def test_retrieves_active_memory_by_predicate() -> None:
    _, _, service = build_service()

    stored = service.remember(
        language_candidate("Python")
    )

    assert stored is not None

    retrieved = service.get_active_memory(
        user_id="local_user",
        intelligence_id="default",
        predicate="preferred_implementation_language",
        subject="user",
        namespace="implementation_preferences",
        record_access=False,
    )

    assert retrieved is not None
    assert retrieved.memory_id == stored.memory_id
    assert retrieved.value == "Python"
    assert retrieved.status is MemoryStatus.ACTIVE


def test_single_value_preference_supersedes_previous_value() -> None:
    _, repository, service = build_service()

    python_memory = service.remember(
        language_candidate("Python")
    )

    typescript_memory = service.remember(
        language_candidate("TypeScript")
    )

    assert python_memory is not None
    assert typescript_memory is not None

    active = service.get_active_memory(
        user_id="local_user",
        intelligence_id="default",
        predicate="preferred_implementation_language",
        subject="user",
        namespace="implementation_preferences",
        record_access=False,
    )

    assert active is not None
    assert active.memory_id == typescript_memory.memory_id
    assert active.value == "TypeScript"
    assert active.status is MemoryStatus.ACTIVE
    assert active.supersedes_memory_id == python_memory.memory_id

    previous = repository.get(
        user_id="local_user",
        intelligence_id="default",
        memory_id=str(python_memory.memory_id),
    )

    assert previous is not None
    assert previous.value == "Python"
    assert previous.status is MemoryStatus.SUPERSEDED


def test_equivalent_value_confirms_existing_record() -> None:
    _, _, service = build_service()

    first = service.remember(
        language_candidate("Python")
    )

    second = service.remember(
        language_candidate("Python")
    )

    assert first is not None
    assert second is not None
    assert first.memory_id == second.memory_id
    assert second.metadata["confirmation_count"] == 2


def test_direct_retrieval_records_access() -> None:
    _, _, service = build_service()

    stored = service.remember(
        language_candidate("Python")
    )

    assert stored is not None
    assert stored.access_count == 0

    accessed = service.get_active_memory(
        user_id="local_user",
        intelligence_id="default",
        predicate="preferred_implementation_language",
        namespace="implementation_preferences",
    )

    assert accessed is not None
    assert accessed.access_count == 1
    assert accessed.last_accessed_at is not None


def test_missing_predicate_returns_none() -> None:
    _, _, service = build_service()

    result = service.get_active_memory(
        user_id="local_user",
        intelligence_id="default",
        predicate="preferred_response_style",
        namespace="interaction_preferences",
        record_access=False,
    )

    assert result is None
