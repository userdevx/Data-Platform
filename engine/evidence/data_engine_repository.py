from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from engine.evidence.serialization import (
    ENTITY_TYPE_BY_CLASS,
    deserialize_entity,
    serialize_entity,
)


WriteRecord = Callable[
    [dict[str, Any]],
    None,
]

ReadEntityRecord = Callable[
    [UUID],
    dict[str, Any] | None,
]

QueryRecords = Callable[
    [str | None],
    list[dict[str, Any]],
]


class PlatformDataEngineRepository:
    """
    Evidence repository backed by the Data Engine.

    Persistence is available only through the injected Data Engine
    callables. This repository owns no independent storage.

    Entity-to-record translation remains owned by
    engine.evidence.serialization.
    """

    def __init__(
        self,
        *,
        write_record: WriteRecord,
        read_entity_record: ReadEntityRecord,
        query_records: QueryRecords,
    ) -> None:
        for name, callback in (
            ("write_record", write_record),
            (
                "read_entity_record",
                read_entity_record,
            ),
            ("query_records", query_records),
        ):
            if not callable(callback):
                raise TypeError(
                    f"{name} must be callable."
                )

        self._write_record = write_record
        self._read_entity_record = (
            read_entity_record
        )
        self._query_records = query_records

    def save(
        self,
        entity: object,
    ) -> None:
        record = serialize_entity(
            entity
        )

        self._write_record(
            record
        )

    def get(
        self,
        entity_id: UUID,
    ) -> object | None:
        if not isinstance(
            entity_id,
            UUID,
        ):
            raise TypeError(
                "entity_id must be a UUID."
            )

        record = self._read_entity_record(
            entity_id
        )

        if record is None:
            return None

        return deserialize_entity(
            record
        )

    def find(
        self,
        entity_class: type | None = None,
    ) -> list[object]:
        entity_type: str | None = None

        if entity_class is not None:
            entity_type = (
                ENTITY_TYPE_BY_CLASS.get(
                    entity_class
                )
            )

            if entity_type is None:
                raise TypeError(
                    "Unsupported Evidence entity class: "
                    f"{entity_class.__name__}"
                )

        records = self._query_records(
            entity_type
        )

        return [
            deserialize_entity(
                record
            )
            for record in records
        ]
