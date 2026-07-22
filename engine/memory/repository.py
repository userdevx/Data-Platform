from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Protocol

from engine.memory.models import MemoryRecord, MemoryStatus, utc_now


class DataEnginePort(Protocol):
    def store(self, record: dict[str, Any]) -> None:
        ...

    def replace(self, record_id: str, record: dict[str, Any]) -> None:
        ...

    def query(
        self,
        *,
        source: str | None = None,
        category: str | None = None,
        sensor_type: str | None = None,
        metadata_filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def get(self, record_id: str) -> dict[str, Any] | None:
        ...

    def rebuild_index(self, index_name: str) -> None:
        ...


class MemoryRepository:
    def __init__(self, data_engine: DataEnginePort) -> None:
        self._data_engine = data_engine

    def insert(self, memory: MemoryRecord) -> MemoryRecord:
        self._data_engine.store(memory.to_engine_record())
        return memory

    def replace(self, memory: MemoryRecord) -> MemoryRecord:
        self._data_engine.replace(
            str(memory.memory_id),
            memory.to_engine_record(),
        )
        return memory

    def get(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        memory_id: str,
    ) -> MemoryRecord | None:
        raw = self._data_engine.get(memory_id)

        if raw is None:
            return None

        memory = MemoryRecord.from_engine_record(raw)

        if memory.user_id != user_id:
            return None

        if memory.intelligence_id != intelligence_id:
            return None

        return memory

    def list_active(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        namespace: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]:
        filters: dict[str, Any] = {
            "user_id": user_id,
            "intelligence_id": intelligence_id,
            "status": MemoryStatus.ACTIVE.value,
        }

        if namespace is not None:
            filters["namespace"] = namespace

        raw_records = self._data_engine.query(
            source="intelligence",
            category="memory",
            metadata_filters=filters,
            limit=limit,
        )

        memories = [
            MemoryRecord.from_engine_record(record)
            for record in raw_records
        ]

        current_memories = [
            memory
            for memory in memories
            if memory.is_current()
        ]

        current_memories.sort(
            key=lambda memory: memory.updated_at,
            reverse=True,
        )

        return current_memories

    def list_all(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        namespace: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]:
        filters: dict[str, Any] = {
            "user_id": user_id,
            "intelligence_id": intelligence_id,
        }

        if namespace is not None:
            filters["namespace"] = namespace

        raw_records = self._data_engine.query(
            source="intelligence",
            category="memory",
            metadata_filters=filters,
            limit=limit,
        )

        memories = [
            MemoryRecord.from_engine_record(record)
            for record in raw_records
        ]

        memories.sort(
            key=lambda memory: memory.updated_at,
            reverse=True,
        )

        return memories

    def get_active_memory(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        predicate: str,
        subject: str = "user",
        namespace: str | None = None,
    ) -> MemoryRecord | None:
        filters: dict[str, Any] = {
            "user_id": user_id,
            "intelligence_id": intelligence_id,
            "status": MemoryStatus.ACTIVE.value,
        }

        if namespace is not None:
            filters["namespace"] = namespace

        raw_records = self._data_engine.query(
            source="intelligence",
            category="memory",
            metadata_filters=filters,
        )

        matches: list[MemoryRecord] = []

        for raw_record in raw_records:
            memory = MemoryRecord.from_engine_record(raw_record)

            if memory.user_id != user_id:
                continue

            if memory.intelligence_id != intelligence_id:
                continue

            if memory.status is not MemoryStatus.ACTIVE:
                continue

            if memory.subject != subject:
                continue

            if memory.predicate != predicate:
                continue

            if namespace is not None and memory.namespace != namespace:
                continue

            if not memory.is_current():
                continue

            matches.append(memory)

        if not matches:
            return None

        matches.sort(
            key=lambda memory: memory.updated_at,
            reverse=True,
        )

        return matches[0]

    def find_identity_matches(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        namespace: str,
        subject: str,
        predicate: str,
    ) -> list[MemoryRecord]:
        memories = self.list_active(
            user_id=user_id,
            intelligence_id=intelligence_id,
            namespace=namespace,
        )

        return [
            memory
            for memory in memories
            if (
                memory.subject == subject
                and memory.predicate == predicate
            )
        ]

    def mark_superseded(
        self,
        memory: MemoryRecord,
    ) -> MemoryRecord:
        updated = replace(
            memory,
            status=MemoryStatus.SUPERSEDED,
            updated_at=utc_now(),
        )

        return self.replace(updated)

    def mark_deleted(
        self,
        memory: MemoryRecord,
    ) -> MemoryRecord:
        updated = replace(
            memory,
            status=MemoryStatus.DELETED,
            updated_at=utc_now(),
        )

        return self.replace(updated)

    def mark_expired(
        self,
        memory: MemoryRecord,
    ) -> MemoryRecord:
        updated = replace(
            memory,
            status=MemoryStatus.EXPIRED,
            updated_at=utc_now(),
        )

        return self.replace(updated)

    def record_access(
        self,
        memory: MemoryRecord,
    ) -> MemoryRecord:
        now = utc_now()

        updated = replace(
            memory,
            access_count=memory.access_count + 1,
            last_accessed_at=now,
            updated_at=now,
        )

        return self.replace(updated)

    def find_expired(
        self,
        *,
        now: datetime,
    ) -> list[MemoryRecord]:
        raw_records = self._data_engine.query(
            source="intelligence",
            category="memory",
            metadata_filters={
                "status": MemoryStatus.ACTIVE.value,
            },
        )

        expired: list[MemoryRecord] = []

        for raw_record in raw_records:
            memory = MemoryRecord.from_engine_record(raw_record)

            if (
                memory.valid_until is not None
                and memory.valid_until <= now
            ):
                expired.append(memory)

        return expired

    def rebuild_memory_index(self) -> None:
        self._data_engine.rebuild_index("memory")
