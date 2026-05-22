import os
import shutil

from engine.lakehouse_query import query_lakehouse_partition
from engine.storage.jsonl_backend import LocalJsonlAppendBackend


def test_query_lakehouse_partition_filters_records():
    test_dir = "./test_query_lakehouse"

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    backend = LocalJsonlAppendBackend(base_dir=test_dir)

    records = [
        {
            "source": "edge_device",
            "category": "motion",
            "sensor_type": "pir_motion_sensor",
            "value": True,
            "unit": "boolean",
        },
        {
            "source": "system",
            "category": "device_status",
            "sensor_type": "cpu_temperature",
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
        sensor_type="pir_motion_sensor",
        base_dir=test_dir,
    )

    assert result["records_scanned"] == 2
    assert result["records_returned"] == 1
    assert result["data"][0]["sensor_type"] == "pir_motion_sensor"

    shutil.rmtree(test_dir)
