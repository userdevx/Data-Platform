import os
import shutil

from engine.storage.jsonl_backend import LocalJsonlAppendBackend


def test_jsonl_append_backend_writes_lakehouse_file():
    test_dir = "./test_data_lake"

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    backend = LocalJsonlAppendBackend(base_dir=test_dir)

    record = {
        "source": "edge_device",
        "category": "motion",
        "sensor_type": "pir_motion_sensor",
        "value": True,
        "unit": "boolean",
    }

    backend.append_record(
        zone="raw",
        namespace="sensor_events",
        partition="2026-05-14",
        record=record,
    )

    expected_path = os.path.join(
        test_dir,
        "raw",
        "sensor_events",
        "partition=2026-05-14",
        "data.jsonl",
    )

    assert os.path.exists(expected_path)

    records = backend.read_records(
        zone="raw",
        namespace="sensor_events",
        partition="2026-05-14",
    )

    assert len(records) == 1
    assert records[0]["source"] == "edge_device"
    assert records[0]["sensor_type"] == "pir_motion_sensor"
    assert records[0]["_lakehouse"]["zone"] == "raw"

    shutil.rmtree(test_dir)
