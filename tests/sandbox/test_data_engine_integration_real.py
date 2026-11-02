from __future__ import annotations

from engine.sandbox.data_engine import (
    CANONICAL_FIELDS,
    sandbox_result_record,
)


def test_sandbox_record_uses_exact_data_engine_schema() -> None:
    record = sandbox_result_record(
        execution_id="exec-1",
        runtime_kind="firecracker",
        isolation_class="hardware",
        exit_code=0,
        timed_out=False,
        duration_seconds=1.25,
        stdout="ok\n",
        stderr="",
    )

    assert tuple(record) == CANONICAL_FIELDS

    assert tuple(record) == (
        "source",
        "category",
        "data_type",
        "value",
        "unit",
    )

    assert "sensor_type" not in record
    assert record["source"] == "sandbox"
    assert record["data_type"] == "sandbox_result"


def test_sandbox_result_persists_through_real_data_engine(tmp_path):
    from engine.data_engine.record_writer import DataEngineRecordWriter
    from engine.query import QueryService
    from engine.storage.json_backend import LocalJsonStorageBackend

    storage_path = tmp_path / "sandbox_records.json"

    writer = DataEngineRecordWriter(
        query_service=QueryService(
            LocalJsonStorageBackend(str(storage_path))
        )
    )

    record = sandbox_result_record(
        execution_id="real-persistence-1",
        runtime_kind="gvisor",
        isolation_class="kernel_emulation",
        exit_code=0,
        timed_out=False,
        duration_seconds=0.5,
        stdout="verified",
        stderr="",
    )

    assert record["unit"] == "record"

    stored = writer.write(**record)
    assert stored is not None
    assert storage_path.is_file()

    reopened = QueryService(
        LocalJsonStorageBackend(str(storage_path))
    )

    records = reopened.get_all_records()
    assert len(records) == 1

    persisted = records[0]

    assert persisted["source"] == "sandbox"
    assert persisted["category"] == "execution"
    assert persisted["data_type"] == "sandbox_result"
    assert persisted["unit"] == "record"
    assert persisted["value"]["execution_id"] == "real-persistence-1"
    assert persisted["value"]["runtime_kind"] == "gvisor"
    assert persisted["value"]["exit_code"] == 0
    assert "sensor_type" not in persisted
