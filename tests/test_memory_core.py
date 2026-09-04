from __future__ import annotations

from copy import deepcopy
from typing import Any

from engine.memory.context_builder import MemoryContextBuilder
from engine.memory.models import MemoryCandidate, MemoryKind
from engine.memory.repository import MemoryRepository
from engine.memory.retrieval import MemoryRetriever
from engine.memory.service import MemoryService
from engine.memory.validation import MemoryValidator


class InMemoryDataEngine:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.rebuilt_indexes: list[str] = []

    def store(self, record: dict[str, Any]) -> None:
        self.records[record["record_id"]] = deepcopy(record)

    def replace(self, record_id: str, record: dict[str, Any]) -> None:
        self.records[record_id] = deepcopy(record)

    def get(self, record_id: str) -> dict[str, Any] | None:
        record = self.records.get(record_id)
        return deepcopy(record) if record else None

    def query(
        self,
        *,
        source: str | None = None,
        category: str | None = None,
        data_type: str | None = None,
        metadata_filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for record in self.records.values():
            if source and record.get("source") != source:
                continue

            if category and record.get("category") != category:
                continue

            if data_type and record.get("data_type") != data_type:
                continue

            metadata = record.get("metadata", {})

            if metadata_filters:
                if any(metadata.get(key) != value for key, value in metadata_filters.items()):
                    continue

            results.append(deepcopy(record))

        if limit is not None:
            return results[:limit]

        return results

    def rebuild_index(self, index_name: str) -> None:
        self.rebuilt_indexes.append(index_name)


def build_service() -> MemoryService:
    data_engine = InMemoryDataEngine()

    return MemoryService(
        repository=MemoryRepository(data_engine),
        validator=MemoryValidator(),
        retriever=MemoryRetriever(),
        context_builder=MemoryContextBuilder(),
    )


def test_store_and_retrieve_memory() -> None:
    service = build_service()

    stored = service.remember(
        MemoryCandidate(
            user_id="user-1",
            intelligence_id="primary_intelligence",
            namespace="implementation_preferences",
            kind=MemoryKind.PROCEDURAL,
            subject="user",
            predicate="preferred_implementation_language",
            value="Python",
            canonical_text="The user prefers Python implementations.",
            confidence=0.98,
            importance=0.90,
            source_text="I prefer Python.",
            explicit_request=True,
        )
    )

    assert stored is not None
    assert stored.value == "Python"

    memories = service.retrieve(
        user_id="user-1",
        intelligence_id="primary_intelligence",
        query="Write an implementation example.",
    )

    assert len(memories) == 1
    assert memories[0].value == "Python"


def test_memory_context_is_generated() -> None:
    service = build_service()

    service.remember(
        MemoryCandidate(
            user_id="user-1",
            intelligence_id="primary_intelligence",
            namespace="project_rules",
            kind=MemoryKind.PROCEDURAL,
            subject="active_project",
            predicate="project_rule",
            value="Use the Data Engine as the source of truth.",
            canonical_text="Use the Data Engine as the source of truth.",
            confidence=0.99,
            importance=1.0,
            source_text="Always use the Data Engine as the source of truth.",
            explicit_request=True,
        )
    )

    context = service.build_context(
        user_id="user-1",
        intelligence_id="primary_intelligence",
        query="How should memory be stored?",
    )

    assert "<user_memory>" in context
    assert "Data Engine" in context


def test_memory_isolation_by_intelligence_id() -> None:
    service = build_service()

    service.remember(
        MemoryCandidate(
            user_id="user-1",
            intelligence_id="intelligence-a",
            namespace="implementation_preferences",
            kind=MemoryKind.PROCEDURAL,
            subject="user",
            predicate="preferred_implementation_language",
            value="Python",
            canonical_text="The user prefers Python implementations.",
            confidence=0.99,
            importance=0.90,
            source_text="I prefer Python.",
            explicit_request=True,
        )
    )

    memories = service.list_memories(
        user_id="user-1",
        intelligence_id="intelligence-b",
    )

    assert memories == []


def test_single_value_memory_supersedes_old_value() -> None:
    service = build_service()

    first = service.remember(
        MemoryCandidate(
            user_id="user-1",
            intelligence_id="primary_intelligence",
            namespace="implementation_preferences",
            kind=MemoryKind.PROCEDURAL,
            subject="user",
            predicate="preferred_implementation_language",
            value="Java",
            canonical_text="The user prefers Java implementations.",
            confidence=0.95,
            importance=0.85,
            source_text="I prefer Java.",
            explicit_request=True,
        )
    )

    second = service.remember(
        MemoryCandidate(
            user_id="user-1",
            intelligence_id="primary_intelligence",
            namespace="implementation_preferences",
            kind=MemoryKind.PROCEDURAL,
            subject="user",
            predicate="preferred_implementation_language",
            value="Python",
            canonical_text="The user prefers Python implementations.",
            confidence=0.99,
            importance=0.95,
            source_text="I switched from Java to Python.",
            explicit_request=True,
        )
    )

    active = service.list_memories(
        user_id="user-1",
        intelligence_id="primary_intelligence",
    )

    assert first is not None
    assert second is not None
    assert second.supersedes_memory_id == first.memory_id
    assert len(active) == 1
    assert active[0].value == "Python"
