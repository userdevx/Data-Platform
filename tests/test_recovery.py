import json
from pathlib import Path

import engine.recovery as recovery


def test_recovery_check_completes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        recovery,
        "DATA_FILE",
        "data/records.json",
    )
    monkeypatch.setattr(
        recovery,
        "BACKUP_FILE",
        "data/records.json.backup",
    )
    monkeypatch.setattr(
        recovery,
        "JOB_DIR",
        "data/jobs",
    )
    monkeypatch.setattr(
        recovery,
        "LOG_DIR",
        "logs",
    )

    report = recovery.run_recovery_check()

    data_file = tmp_path / "data" / "records.json"
    job_dir = tmp_path / "data" / "jobs"
    log_dir = tmp_path / "logs"

    assert report["status"] == "recovery_check_complete"

    assert report["data"]["file"] == "data/records.json"
    assert report["data"]["status"] == "missing"
    assert report["data"]["backup_status"] == "missing"
    assert (
        report["data"]["action"]
        == "created_empty_data_file"
    )

    assert len(report["jobs"]) == len(recovery.JOB_FILES)

    assert report["logs"] == {
        "directory": "logs",
        "status": "ready",
        "action": "ensured_directory_exists",
    }

    assert data_file.is_file()
    assert job_dir.is_dir()
    assert log_dir.is_dir()

    stored_data = json.loads(
        data_file.read_text(encoding="utf-8")
    )

    assert stored_data == []

    for job_report, job_file_name in zip(
        report["jobs"],
        recovery.JOB_FILES,
        strict=True,
    ):
        expected_relative_path = (
            f"data/jobs/{job_file_name}"
        )
        job_file = job_dir / job_file_name

        assert job_report["file"] == expected_relative_path
        assert job_report["status"] == "missing"
        assert (
            job_report["action"]
            == "created_empty_job_file"
        )

        assert job_file.is_file()

        stored_jobs = json.loads(
            job_file.read_text(encoding="utf-8")
        )

        assert stored_jobs == []
