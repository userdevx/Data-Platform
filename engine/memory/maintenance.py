from __future__ import annotations

from dataclasses import dataclass

from engine.memory.models import utc_now
from engine.memory.repository import MemoryRepository


@dataclass(slots=True)
class MaintenanceResult:
    expired_count: int
    index_rebuilt: bool


class MemoryMaintenance:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    def run(self) -> MaintenanceResult:
        now = utc_now()
        expired = self._repository.find_expired(now=now)

        for memory in expired:
            self._repository.mark_expired(memory)

        self._repository.rebuild_memory_index()

        return MaintenanceResult(
            expired_count=len(expired),
            index_rebuilt=True,
        )
