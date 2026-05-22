import os
import shutil

from engine.storage.parquet_backend import LocalParquetStorageBackend


def test_parquet_backend_writes_and_reads_records():
    test_dir = "./test_parquet_lake"

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    backend = LocalParquetStorageBackend(base_dir=test_dir)

    records = [
        {
            "source": "edge_device",
            "category": "motion",
            "sensor_type": "pir_motion_sensor",
            "value": True,
            "unit": "boolean",
        },
        {
            "source": "edge_device",
            "category": "motion",
            "sensor_type": "pir_motion_sensor",
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

    assert os.path.exists(file_path)
    assert file_path.endswith("data.parquet")

    retrieved_records = backend.read_records(
        zone="silver",
        namespace="motion_events",
        partition="2026-05-15",
    )

    assert len(retrieved_records) == 2
    assert retrieved_records[0]["sensor_type"] == "pir_motion_sensor"

    shutil.rmtree(test_dir)
