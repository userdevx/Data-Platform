from pathlib import Path

from engine.storage.parquet_backend import LocalParquetStorageBackend


def test_parquet_backend_writes_and_reads_records(
    tmp_path: Path,
) -> None:
    test_dir = tmp_path / "test_parquet_lake"

    backend = LocalParquetStorageBackend(
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
            "source": "edge_device",
            "category": "motion",
            "data_type": "pir_motion_sensor",
            "value": False,
            "unit": "boolean",
        },
    ]

    file_path = backend.write_records(
        zone="silver",
        namespace="motion_events",
        partition="2026-05-15",
        records=records,
    )

    stored_path = Path(file_path)

    assert stored_path.is_file()
    assert test_dir in stored_path.parents

    stored_records = backend.read_records(
        zone="silver",
        namespace="motion_events",
        partition="2026-05-15",
    )

    assert len(stored_records) == 2
    assert stored_records[0]["source"] == "edge_device"
    assert stored_records[0]["category"] == "motion"
    assert stored_records[0]["data_type"] == "pir_motion_sensor"
    assert stored_records[0]["value"] is True
    assert stored_records[1]["value"] is False
