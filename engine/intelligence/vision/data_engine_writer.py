from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from engine.storage.loader import StorageBackendLoader


VISUAL_NAMESPACE = "intelligence.visual"
VISUAL_SCHEMA_VERSION = "1"
_WRITE_LOCK = Lock()


def visual_partition(
    *,
    created_at: str | None = None,
) -> str:
    timestamp = (
        datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )
        if created_at
        else datetime.now(UTC)
    )

    return timestamp.astimezone(UTC).strftime(
        "%Y-%m-%d"
    )


class DataEngineVisualRecordWriter:
    def __init__(
        self,
        *,
        namespace: str = VISUAL_NAMESPACE,
        version: str = VISUAL_SCHEMA_VERSION,
    ) -> None:
        clean_namespace = namespace.strip()
        clean_version = version.strip()

        if not clean_namespace:
            raise ValueError(
                "namespace is required."
            )

        if not clean_version:
            raise ValueError(
                "version is required."
            )

        self.namespace = clean_namespace
        self.version = clean_version

    def __call__(
        self,
        record: dict[str, Any],
    ) -> None:
        self.write(record)

    def write(
        self,
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = self._normalize_record(
            record
        )

        partition = visual_partition(
            created_at=normalized["created_at"]
        )

        backend = (
            StorageBackendLoader.get_backend()
        )

        with _WRITE_LOCK:
            existing = backend.read_records(
                namespace=self.namespace,
                partition=partition,
                version=self.version,
            )

            self._reject_duplicate(
                existing=existing,
                record_id=normalized["id"],
            )

            updated = [
                *existing,
                normalized,
            ]

            backend.write_records(
                namespace=self.namespace,
                partition=partition,
                version=self.version,
                records=updated,
            )

        return normalized

    @staticmethod
    def _normalize_record(
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(record)

        record_id = str(
            normalized.get("id", "")
        ).strip()

        record_type = str(
            normalized.get("record_type", "")
        ).strip()

        created_at = str(
            normalized.get("created_at", "")
        ).strip()

        if not record_id:
            raise ValueError(
                "Visual Data Engine records require an id."
            )

        if not record_type:
            raise ValueError(
                "Visual Data Engine records require "
                "a record_type."
            )

        if not created_at:
            created_at = (
                datetime.now(UTC).isoformat()
            )

        if not isinstance(
            normalized.get("data"),
            dict,
        ):
            raise ValueError(
                "Visual Data Engine records require "
                "a data object."
            )

        normalized["id"] = record_id
        normalized["record_type"] = record_type
        normalized["created_at"] = created_at
        normalized["source"] = str(
            normalized.get(
                "source",
                "visual_analysis",
            )
        ).strip()
        normalized["category"] = str(
            normalized.get(
                "category",
                "runtime_evidence",
            )
        ).strip()

        return normalized

    @staticmethod
    def _reject_duplicate(
        *,
        existing: list[dict[str, Any]],
        record_id: str,
    ) -> None:
        for item in existing:
            if str(
                item.get("id", "")
            ).strip() == record_id:
                raise ValueError(
                    "A visual record with this id "
                    "already exists."
                )
