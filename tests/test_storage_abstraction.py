import os
import shutil

from engine.storage.loader import StorageBackendLoader


def test_engine_storage_abstraction():
    test_dir = "./test_warehouse"

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

    backend = StorageBackendLoader.configure(
        backend_type="local_json",
        base_dir=test_dir,
    )

    namespace = "analytics.user_clicks"
    partition = "2026-05-14"
    version = "1"

    records = [
        {"click_id": "c1", "user_id": 42},
        {"click_id": "c2", "user_id": 99},
    ]

    backend.write_records(
        namespace=namespace,
        partition=partition,
        version=version,
        records=records,
    )

    expected_path = os.path.join(
        test_dir,
        "analytics",
        "user_clicks",
        "partition=2026-05-14",
        "data_v1.json",
    )

    assert os.path.exists(expected_path)

    retrieved_records = backend.read_records(
        namespace=namespace,
        partition=partition,
        version=version,
    )

    assert len(retrieved_records) == 2
    assert retrieved_records[0]["user_id"] == 42

    shutil.rmtree(test_dir)
