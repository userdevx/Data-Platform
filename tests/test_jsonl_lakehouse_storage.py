from pathlib import Path

from engine.storage.jsonl_backend import LocalJsonlAppendBackend


def test_jsonl_append_backend_writes_lakehouse_file(
    tmp_path: Path,
) -> None:
    test_dir = tmp_path / "test_data_lake"

    backend = LocalJsonlAppendBackend(
        base_dir=str(test_dir),
    )

    record = {
        "source": "edge_device",
        "category": "motion",
        "data_type": "pir_motion_sensor",
        "value": True,
        "unit": "boolean",
    }

    backend.append_record(
        zone="raw",
        namespace="sensor_events",
        partition="2026-05-14",
        record=record,
    )

    expected_path = (
        test_dir
        / "raw"
        / "sensor_events"
        / "partition=2026-05-14"
        / "data.jsonl"
    )

    assert expected_path.is_file()
    assert test_dir in expected_path.parents

    records = backend.read_records(
        zone="raw",
        namespace="sensor_events",
        partition="2026-05-14",
    )

    assert len(records) == 1
    assert records[0]["source"] == "edge_device"
    assert records[0]["category"] == "motion"
    assert records[0]["data_type"] == "pir_motion_sensor"
    assert records[0]["value"] is True
    assert records[0]["unit"] == "boolean"

    lakehouse_metadata = records[0]["_lakehouse"]

    assert lakehouse_metadata["zone"] == "raw"
    assert lakehouse_metadata["namespace"] == "sensor_events"
    assert lakehouse_metadata["partition"] == "2026-05-14"
