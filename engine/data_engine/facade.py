from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DataEngineFacade:
    """
    Generic Data Engine facade for normalized records.

    This is not a separate memory store.
    Memory records are stored as normal Data Engine records with:

        source = intelligence
        category = memory
    """

    def __init__(
        self,
        *,
        root: Path,
        records_path: str = "data/records.json",
    ) -> None:
        self.root = root
        self.records_path = root / records_path
        self.index_dir = root / "data" / "indexes"

    def connect(self) -> DataEngineFacade:
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        if not self.records_path.exists():
            self._write_payload([])

        return self

    def store(self, record: dict[str, Any]) -> None:
        payload = self._read_payload()
        records = self._records_from_payload(payload)

        records.append(record)

        self._write_payload_from_records(payload, records)

    def replace(self, record_id: str, record: dict[str, Any]) -> None:
        payload = self._read_payload()
        records = self._records_from_payload(payload)

        replaced = False

        for index, current in enumerate(records):
            if str(current.get("record_id", current.get("id", ""))) == str(record_id):
                records[index] = record
                replaced = True
                break

        if not replaced:
            records.append(record)

        self._write_payload_from_records(payload, records)

    def get(self, record_id: str) -> dict[str, Any] | None:
        payload = self._read_payload()
        records = self._records_from_payload(payload)

        for record in records:
            if str(record.get("record_id", record.get("id", ""))) == str(record_id):
                return record

        return None

    def query(
        self,
        *,
        source: str | None = None,
        category: str | None = None,
        sensor_type: str | None = None,
        metadata_filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._read_payload()
        records = self._records_from_payload(payload)

        results: list[dict[str, Any]] = []

        for record in records:
            if source is not None and record.get("source") != source:
                continue

            if category is not None and record.get("category") != category:
                continue

            if sensor_type is not None and record.get("sensor_type") != sensor_type:
                continue

            metadata = record.get("metadata", {})

            if metadata_filters:
                if any(metadata.get(key) != value for key, value in metadata_filters.items()):
                    continue

            results.append(record)

            if limit is not None and len(results) >= limit:
                break

        return results

    def update(self, record_id: str, changes: dict[str, Any]) -> None:
        existing = self.get(record_id)

        if existing is None:
            raise KeyError(f"Record not found: {record_id}")

        updated = {
            **existing,
            **changes,
        }

        self.replace(record_id, updated)

    def delete(self, record_id: str) -> None:
        payload = self._read_payload()
        records = self._records_from_payload(payload)

        records = [
            record
            for record in records
            if str(record.get("record_id", record.get("id", ""))) != str(record_id)
        ]

        self._write_payload_from_records(payload, records)

    def rebuild_index(self, index_name: str) -> None:
        if index_name != "memory":
            return

        payload = self._read_payload()
        records = self._records_from_payload(payload)

        memory_records = [
            record
            for record in records
            if record.get("source") == "intelligence"
            and record.get("category") == "memory"
        ]

        index = {
            "index_name": "memory",
            "record_count": len(memory_records),
            "records": [
                {
                    "record_id": record.get("record_id"),
                    "sensor_type": record.get("sensor_type"),
                    "metadata": record.get("metadata", {}),
                    "value": record.get("value", {}),
                }
                for record in memory_records
            ],
        }

        self.index_dir.mkdir(parents=True, exist_ok=True)
        (self.index_dir / "memory_index.json").write_text(
            json.dumps(index, indent=2),
            encoding="utf-8",
        )

    def _read_payload(self) -> Any:
        self.connect()

        try:
            text = self.records_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return []

        if not text:
            return []

        return json.loads(text)

    def _write_payload(self, payload: Any) -> None:
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        self.records_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _records_from_payload(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            records = payload.get("records")

            if isinstance(records, list):
                return records

            data = payload.get("data")

            if isinstance(data, list):
                return data

        return []

    def _write_payload_from_records(
        self,
        original_payload: Any,
        records: list[dict[str, Any]],
    ) -> None:
        if isinstance(original_payload, dict):
            if isinstance(original_payload.get("records"), list):
                updated = {
                    **original_payload,
                    "records": records,
                }
                self._write_payload(updated)
                return

            if isinstance(original_payload.get("data"), list):
                updated = {
                    **original_payload,
                    "data": records,
                }
                self._write_payload(updated)
                return

        self._write_payload(records)
