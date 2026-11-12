from pathlib import Path

import pytest

from engine.application_engineering.aider_worker import (
    WorkerState,
    validate_request,
)
from engine.data_engine.record_writer import DataEngineRecordWriter
from engine.query import QueryService
from engine.storage.json_backend import LocalJsonStorageBackend


def make_environment(tmp_path: Path):
    root = tmp_path / "generated-applications"
    root.mkdir()

    workspace = root / "app-001"
    workspace.mkdir()

    (workspace / "main.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    return root, workspace


def request_payload():
    return {
        "action": "submit",
        "workspace": "app-001",
        "request": "Implement the requested application.",
        "target_files": ["main.py"],
    }


def test_valid_managed_workspace(tmp_path):
    root, workspace = make_environment(tmp_path)

    result = validate_request(request_payload(), root)

    assert result["workspace"] == str(workspace.resolve())
    assert result["target_files"] == ["main.py"]


def test_reject_workspace_traversal(tmp_path):
    root, _ = make_environment(tmp_path)

    payload = request_payload()
    payload["workspace"] = "../outside"

    with pytest.raises(ValueError):
        validate_request(payload, root)


def test_reject_target_escape(tmp_path):
    root, _ = make_environment(tmp_path)

    payload = request_payload()
    payload["target_files"] = ["../../outside.py"]

    with pytest.raises(ValueError):
        validate_request(payload, root)


def test_reject_symlink(tmp_path):
    root, workspace = make_environment(tmp_path)

    (workspace / "linked.py").symlink_to("/etc/passwd")

    payload = request_payload()
    payload["target_files"] = ["linked.py"]

    with pytest.raises(ValueError):
        validate_request(payload, root)


def test_reject_untrusted_approval(tmp_path):
    root, _ = make_environment(tmp_path)

    payload = request_payload()
    payload["approved"] = True

    with pytest.raises(ValueError):
        validate_request(payload, root)


def test_real_data_engine_persistence(tmp_path):
    """Queued coding jobs survive a fresh Data Engine read."""
    from engine.application_engineering.coding_jobs import (
        CodingJobs,
        JOB_TYPE,
    )
    from engine.storage.json_backend import (
        LocalJsonStorageBackend,
    )

    root, _ = make_environment(tmp_path)
    database_path = tmp_path / "records.json"

    state = WorkerState(root)

    # Test storage is isolated from the real Data Engine.
    state.jobs = CodingJobs(
        backend=LocalJsonStorageBackend(
            str(database_path)
        ),
        project_root=tmp_path,
    )

    result = state.handle(request_payload())

    assert result["status"] == "queued"
    assert result["recorded"] is True
    assert result["coding_executed"] is False
    assert result["engineering_verified"] is False

    # Independently reopen persistent storage.
    fresh_backend = LocalJsonStorageBackend(
        str(database_path)
    )

    records = fresh_backend.get_all_records()

    matching = [
        record
        for record in records
        if record.get("data_type") == JOB_TYPE
        and isinstance(record.get("value"), dict)
        and record["value"].get("execution_id")
            == result["execution_id"]
    ]

    assert len(matching) == 1

    record = matching[0]

    assert record["source"] == "application_engineering"
    assert record["category"] == "application_engineering"
    assert record["unit"] == "record"
    assert "sensor_type" not in record

    restarted = CodingJobs(
        backend=fresh_backend,
        project_root=tmp_path,
    )

    persisted = restarted.status(
        result["execution_id"]
    )

    assert persisted["status"] == "queued"
    assert persisted["coding_executed"] is False
    assert persisted["engineering_verified"] is False



def test_worker_health(tmp_path):
    """Health reflects actual dispatcher state."""
    from engine.application_engineering.coding_jobs import (
        CodingJobs,
    )
    from engine.storage.json_backend import (
        LocalJsonStorageBackend,
    )

    root, _ = make_environment(tmp_path)
    state = WorkerState(root)

    state.jobs = CodingJobs(
        backend=LocalJsonStorageBackend(
            str(tmp_path / "health-records.json")
        ),
        project_root=tmp_path,
    )

    result = state.handle({"action": "health"})

    assert result["status"] == "ready"
    assert result["component"] == (
        "application_engineering_worker"
    )

    # The dispatcher has not been started in this test.
    assert result["coding_execution_enabled"] is False

    # Ordinary coding requests no longer require
    # a separate approval before entering the queue.
    assert result["approval_required"] is False

