import json
from pathlib import Path

from engine.storage.loader import StorageBackendLoader


def test_engine_storage_abstraction(
    tmp_path: Path,
) -> None:
    test_dir = tmp_path / "test_warehouse"

    backend = StorageBackendLoader.configure(
        backend_type="local_json",
        base_dir=str(test_dir),
    )

    namespace = "analytics.user_clicks"
    partition = "2026-05-14"
    version = "1"

    records = [
        {
            "click_id": "c1",
            "user_id": 42,
        },
        {
            "click_id": "c2",
            "user_id": 99,
        },
    ]

    result = backend.write_records(
        namespace=namespace,
        partition=partition,
        version=version,
        records=records,
    )

    assert result is None

    expected_file = (
        test_dir
        / "analytics"
        / "user_clicks"
        / f"partition={partition}"
        / f"data_v{version}.json"
    )

    assert expected_file.is_file()

    stored_records = backend.read_records(
        namespace=namespace,
        partition=partition,
        version=version,
    )

    assert stored_records == records

    envelope = json.loads(
        expected_file.read_text(encoding="utf-8")
    )

    assert envelope["metadata"]["schema_version"] == version
    assert envelope["metadata"]["format"] == "JSON"
    assert envelope["metadata"]["namespace"] == namespace
    assert envelope["metadata"]["partition"] == partition
    assert envelope["metadata"]["record_count"] == len(records)
    assert envelope["records"] == records

    temporary_file = Path(f"{expected_file}.tmp")

    assert not temporary_file.exists()
