from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class DataEngineRepository(Protocol):
    """
    Persistence contract for Evidence entities.

    Evidence owns no independent storage. Implementations persist
    through the Data Engine so there is only one system of record.
    """

    def save(
        self,
        entity: object,
    ) -> None:
        """
        Persist one Evidence entity.
        """
        ...

    def get(
        self,
        entity_id: UUID,
    ) -> object | None:
        """
        Return one Evidence entity by identifier, or None.
        """
        ...

    def find(
        self,
        entity_class: type | None = None,
    ) -> list[object]:
        """
        Return stored Evidence entities, optionally filtered by class.
        """
        ...
