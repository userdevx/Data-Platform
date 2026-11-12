"""Real Data Engine tests for automatic coding jobs.

These tests exercise real disk persistence and state
transitions. They do not impersonate a language model.
"""

from pathlib import Path

import pytest

from engine.application_engineering.coding_jobs import (
    CodingJobs,
)
from engine.storage.json_backend import (
    LocalJsonStorageBackend,
)


def make_jobs(tmp_path: Path) -> CodingJobs:
    backend = LocalJsonStorageBackend(
        str(tmp_path / "records.json")
    )

    return CodingJobs(
        backend=backend,
        project_root=tmp_path,
    )


def submit(jobs: CodingJobs):
    return jobs.submit(
        request="Create a Python application",
        workspace="/managed/application-001",
        target_files=["main.py"],
    )


def test_job_persists_across_instances(tmp_path):
    jobs = make_jobs(tmp_path)

    submitted = submit(jobs)

    assert submitted["status"] == "queued"

    restarted = make_jobs(tmp_path)

    status = restarted.status(
        submitted["execution_id"]
    )

    assert status["status"] == "queued"
    assert status["coding_executed"] is False


def test_claim_is_atomic_and_single_use(tmp_path):
    jobs = make_jobs(tmp_path)

    submitted = submit(jobs)

    claimed = jobs.claim_next()

    assert claimed is not None
    assert (
        claimed["execution_id"]
        == submitted["execution_id"]
    )

    assert jobs.claim_next() is None

    assert jobs.status(
        submitted["execution_id"]
    )["status"] == "running"


def test_interrupted_job_is_not_replayed(tmp_path):
    jobs = make_jobs(tmp_path)

    submitted = submit(jobs)

    assert jobs.claim_next() is not None

    restarted = make_jobs(tmp_path)

    interrupted = restarted.reconcile_interrupted()

    assert submitted["execution_id"] in interrupted

    assert restarted.claim_next() is None

    assert restarted.status(
        submitted["execution_id"]
    )["status"] == "interrupted"


def test_completed_job_cannot_execute_twice(tmp_path):
    jobs = make_jobs(tmp_path)

    submitted = submit(jobs)
    claimed = jobs.claim_next()

    assert claimed is not None

    jobs.finish(
        claimed["execution_id"],
        result={
            "exit_code": 0,
            "agent_execution_success": True,
        },
    )

    state = jobs.status(
        submitted["execution_id"]
    )

    assert state["status"] == "completed"
    assert state["agent_execution_success"] is True
    assert state["engineering_verified"] is False

    assert jobs.claim_next() is None

    with pytest.raises(
        RuntimeError,
        match="not in the running state",
    ):
        jobs.finish(
            claimed["execution_id"],
            result={
                "exit_code": 0,
                "agent_execution_success": True,
            },
        )


def test_failed_dispatch_is_recorded(tmp_path):
    jobs = make_jobs(tmp_path)

    submitted = submit(jobs)
    claimed = jobs.claim_next()

    assert claimed is not None

    jobs.finish(
        claimed["execution_id"],
        result=None,
        error="Configured coding agent unavailable",
    )

    state = jobs.status(
        submitted["execution_id"]
    )

    assert state["status"] == "failed"
    assert state["agent_execution_success"] is False
    assert state["engineering_verified"] is False


def test_same_workspace_cannot_run_concurrently(tmp_path):
    jobs = make_jobs(tmp_path)

    first = submit(jobs)
    second = submit(jobs)

    claimed = jobs.claim_next()

    assert claimed["execution_id"] == first["execution_id"]

    assert jobs.claim_next() is None

    jobs.finish(
        first["execution_id"],
        result={
            "exit_code": 0,
            "agent_execution_success": True,
        },
    )

    next_job = jobs.claim_next()

    assert next_job["execution_id"] == second["execution_id"]


def test_missing_exit_code_cannot_succeed(tmp_path):
    jobs = make_jobs(tmp_path)
    submitted = submit(jobs)

    claimed = jobs.claim_next()
    assert claimed is not None

    jobs.finish(
        submitted["execution_id"],
        result={
            "agent_execution_success": True,
        },
    )

    state = jobs.status(submitted["execution_id"])

    assert state["status"] == "failed"
    assert state["agent_execution_success"] is False
    assert state["engineering_verified"] is False


def test_nonzero_exit_code_cannot_succeed(tmp_path):
    jobs = make_jobs(tmp_path)
    submitted = submit(jobs)

    claimed = jobs.claim_next()
    assert claimed is not None

    jobs.finish(
        submitted["execution_id"],
        result={
            "exit_code": 1,
            "agent_execution_success": True,
        },
    )

    state = jobs.status(submitted["execution_id"])

    assert state["status"] == "failed"
    assert state["agent_execution_success"] is False
    assert state["engineering_verified"] is False
