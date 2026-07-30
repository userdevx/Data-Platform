from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from engine.intelligence.vision.data_engine_writer import (
    DataEngineVisualRecordWriter,
    visual_partition,
)
from engine.storage.loader import StorageBackendLoader


def dynamic_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_record() -> dict:
    return {
        "id": dynamic_value("record"),
        "record_type": "visual_observation",
        "source": "visual_analysis",
        "category": "runtime_evidence",
        "created_at": datetime.now(UTC).isoformat(),
        "data": {
            "runtime_value": dynamic_value("value"),
        },
    }


def test_visual_partition_uses_utc_date() -> None:
    created_at = "2026-07-29T03:12:10+00:00"

    assert visual_partition(
        created_at=created_at,
    ) == "2026-07-29"


def test_writer_persists_visual_record(
    tmp_path: Path,
) -> None:
    previous_backend = StorageBackendLoader._instance

    try:
        StorageBackendLoader.configure(
            "local_json",
            str(tmp_path),
        )

        writer = DataEngineVisualRecordWriter(
            namespace=dynamic_value("namespace"),
            version="1",
        )

        record = build_record()
        saved = writer.write(record)

        backend = StorageBackendLoader.get_backend()

        stored = backend.read_records(
            namespace=writer.namespace,
            partition=visual_partition(
                created_at=record["created_at"],
            ),
            version=writer.version,
        )

        assert saved == record
        assert stored == [record]
    finally:
        StorageBackendLoader._instance = previous_backend


def test_writer_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    previous_backend = StorageBackendLoader._instance

    try:
        StorageBackendLoader.configure(
            "local_json",
            str(tmp_path),
        )

        writer = DataEngineVisualRecordWriter(
            namespace=dynamic_value("namespace"),
            version="1",
        )

        record = build_record()

        writer.write(record)

        with pytest.raises(
            ValueError,
            match="already exists",
        ):
            writer.write(record)
    finally:
        StorageBackendLoader._instance = previous_backend


def test_writer_rejects_missing_record_id() -> None:
    writer = DataEngineVisualRecordWriter()

    record = build_record()
    record["id"] = ""

    with pytest.raises(
        ValueError,
        match="require an id",
    ):
        writer.write(record)


def test_writer_rejects_missing_record_type() -> None:
    writer = DataEngineVisualRecordWriter()

    record = build_record()
    record["record_type"] = ""

    with pytest.raises(
        ValueError,
        match="record_type",
    ):
        writer.write(record)


def test_writer_rejects_missing_data_object() -> None:
    writer = DataEngineVisualRecordWriter()

    record = build_record()
    del record["data"]

    with pytest.raises(
        ValueError,
        match="data object",
    ):
        writer.write(record)
