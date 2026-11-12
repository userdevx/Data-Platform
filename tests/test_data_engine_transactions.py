"""Real cross-process Data Engine transaction tests."""

from multiprocessing import get_context
from pathlib import Path

import pytest

from engine.models import DataRecord
from engine.storage.json_backend import LocalJsonStorageBackend


def append_record(database_path: str, count: int) -> None:
    backend = LocalJsonStorageBackend(database_path)

    for _ in range(count):
        def operation(records):
            identifiers = [
                record["id"]
                for record in records
                if isinstance(record, dict)
                and type(record.get("id")) is int
            ]

            next_id = max(identifiers, default=0) + 1

            record = DataRecord.create(
                id=next_id,
                source="application_engineering",
                category="application_engineering",
                data_type="transaction_test",
                value={"sequence": next_id},
                unit="record",
            ).to_dict()

            records.append(record)
            return next_id

        backend.transact_records(operation)


def test_atomic_insert(tmp_path: Path):
    backend = LocalJsonStorageBackend(
        str(tmp_path / "records.json")
    )

    def insert(records):
        record = DataRecord.create(
            id=1,
            source="application_engineering",
            category="application_engineering",
            data_type="transaction_test",
            value={"state": "received"},
            unit="record",
        ).to_dict()

        records.append(record)
        return record["id"]

    result = backend.transact_records(insert)

    assert result == 1

    fresh = LocalJsonStorageBackend(
        str(tmp_path / "records.json")
    )

    records = fresh.get_all_records()

    assert len(records) == 1
    assert records[0]["id"] == 1
    assert records[0]["source"] == "application_engineering"
    assert "sensor_type" not in records[0]


def test_transaction_rollback(tmp_path: Path):
    path = tmp_path / "records.json"
    backend = LocalJsonStorageBackend(str(path))

    before = path.read_bytes()

    def failing_operation(records):
        records.append({"id": 1})
        raise RuntimeError("transaction rejected")

    with pytest.raises(
        RuntimeError,
        match="transaction rejected",
    ):
        backend.transact_records(failing_operation)

    assert path.read_bytes() == before


def test_duplicate_id_rejected(tmp_path: Path):
    path = tmp_path / "records.json"
    backend = LocalJsonStorageBackend(str(path))

    def operation(records):
        for _ in range(2):
            records.append(
                DataRecord.create(
                    id=1,
                    source="application_engineering",
                    category="application_engineering",
                    data_type="duplicate_test",
                    value={"test": True},
                    unit="record",
                ).to_dict()
            )

    with pytest.raises(ValueError, match="Duplicate"):
        backend.transact_records(operation)

    assert backend.get_all_records() == []


def test_real_cross_process_transactions(tmp_path: Path):
    path = str(tmp_path / "concurrent-records.json")

    LocalJsonStorageBackend(path)

    context = get_context("spawn")

    processes = [
        context.Process(
            target=append_record,
            args=(path, 8),
        )
        for _ in range(3)
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join(timeout=30)

        if process.is_alive():
            process.terminate()
            process.join()
            pytest.fail("Transaction process timed out")

        assert process.exitcode == 0

    backend = LocalJsonStorageBackend(path)
    records = backend.get_all_records()

    assert len(records) == 24

    ids = [record["id"] for record in records]

    assert len(set(ids)) == 24
    assert sorted(ids) == list(range(1, 25))

    assert all(
        record["data_type"] == "transaction_test"
        for record in records
    )


def test_existing_records_are_immutable(tmp_path: Path):
    path = tmp_path / "immutable-records.json"
    backend = LocalJsonStorageBackend(str(path))

    def insert(records):
        records.append(
            DataRecord.create(
                id=1,
                source="application_engineering",
                category="application_engineering",
                data_type="approval_event",
                value={"status": "pending"},
                unit="record",
            ).to_dict()
        )

    backend.transact_records(insert)

    before = path.read_bytes()

    def overwrite(records):
        records[0]["value"] = {"status": "approved"}

    with pytest.raises(
        ValueError,
        match="immutable",
    ):
        backend.transact_records(overwrite)

    assert path.read_bytes() == before

    def remove(records):
        records.clear()

    with pytest.raises(
        ValueError,
        match="immutable",
    ):
        backend.transact_records(remove)

    assert path.read_bytes() == before


def test_duplicate_append_rolls_back(tmp_path: Path):
    path = tmp_path / "duplicate-records.json"
    backend = LocalJsonStorageBackend(str(path))

    def insert(records):
        records.append(
            DataRecord.create(
                id=1,
                source="application_engineering",
                category="application_engineering",
                data_type="approval_event",
                value={"status": "pending"},
                unit="record",
            ).to_dict()
        )

    backend.transact_records(insert)

    before = path.read_bytes()

    with pytest.raises(ValueError, match="Duplicate"):
        backend.transact_records(insert)

    assert path.read_bytes() == before


def test_legacy_record_cannot_be_changed(tmp_path: Path):
    path = tmp_path / "legacy-records.json"
    backend = LocalJsonStorageBackend(str(path))

    legacy = {
        "source": "historical",
        "category": "historical",
        "data_type": "old_record",
        "value": "preserved",
        "unit": "record",
    }

    backend.save_records([legacy])

    before = path.read_bytes()

    def alter(records):
        records[0]["value"] = "tampered"

    with pytest.raises(ValueError, match="immutable"):
        backend.transact_records(alter)

    assert path.read_bytes() == before
