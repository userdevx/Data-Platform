from pathlib import Path

from engine.lakehouse_query import query_lakehouse_partition
from engine.storage.jsonl_backend import LocalJsonlAppendBackend


def test_query_lakehouse_partition_filters_records(
    tmp_path: Path,
) -> None:
    test_dir = tmp_path / "test_query_lakehouse"

    backend = LocalJsonlAppendBackend(
        base_dir=str(test_dir),
    )

    records = [
        {
            "source": "edge_device",
            "category": "motion",
            "data_type": "pir_motion_sensor",
            "value": True,
            "unit": "boolean",
        },
        {
            "source": "system",
            "category": "device_status",
            "data_type": "cpu_temperature",
            "value": 52.0,
            "unit": "C",
        },
    ]

    backend.write_records(
        zone="raw",
        namespace="motion_events",
        partition="2026-05-15",
        records=records,
    )

    result = query_lakehouse_partition(
        zone="raw",
        namespace="motion_events",
        partition="2026-05-15",
        data_type="pir_motion_sensor",
        base_dir=str(test_dir),
    )

    assert result["records_scanned"] == 2
    assert result["records_returned"] == 1
    assert len(result["data"]) == 1

    returned_record = result["data"][0]

    assert returned_record["source"] == "edge_device"
    assert returned_record["category"] == "motion"
    assert returned_record["data_type"] == "pir_motion_sensor"
    assert returned_record["value"] is True
    assert returned_record["unit"] == "boolean"
