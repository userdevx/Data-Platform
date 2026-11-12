"""DataWorc durable Application Engineering coding jobs.

An accepted application-development request authorizes coding
within the validated managed workspace.

The existing Aider dispatcher performs model-driven execution.

The Data Engine stores durable job and lifecycle events.

A previously claimed job is never automatically replayed after
an unexpected worker termination.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import traceback

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from engine.backend import get_backend
from engine.models import DataRecord
from engine.application_generation.agent_dispatcher import (
    dispatch_coding_agent,
)

SOURCE = "application_engineering"
CATEGORY = "application_engineering"

JOB_TYPE = "engineering_coding_job"
STATE_TYPE = "engineering_coding_job_state"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def next_record_id(records: list) -> int:
    identifiers = [
        record["id"]
        for record in records
        if isinstance(record, dict)
        and type(record.get("id")) is int
    ]
    return max(identifiers, default=0) + 1


def append_event(
    records: list,
    data_type: str,
    value: dict,
) -> None:
    records.append(
        DataRecord.create(
            id=next_record_id(records),
            source=SOURCE,
            category=CATEGORY,
            data_type=data_type,
            value=value,
            unit="record",
        ).to_dict()
    )


def read_events(records: list, data_type: str) -> list[dict]:
    return [
        record["value"]
        for record in records
        if (
            isinstance(record, dict)
            and record.get("source") == SOURCE
            and record.get("category") == CATEGORY
            and record.get("data_type") == data_type
            and isinstance(record.get("value"), dict)
        )
    ]


def job_snapshot(records: list) -> tuple[dict, dict]:
    jobs = {}
    states = {}

    for event in read_events(records, JOB_TYPE):
        execution_id = event["execution_id"]

        if execution_id in jobs:
            raise RuntimeError(
                "Duplicate coding job identifier"
            )

        jobs[execution_id] = event

    for event in read_events(records, STATE_TYPE):
        execution_id = event["execution_id"]

        if execution_id not in jobs:
            raise RuntimeError(
                "Orphaned coding job state"
            )

        states[execution_id] = event

    return jobs, states


class CodingJobs:
    """Production coding-job lifecycle coordinator."""

    def __init__(
        self,
        *,
        backend=None,
        project_root: Path | None = None,
        dispatcher=None,
    ) -> None:
        self.backend = (
            backend if backend is not None else get_backend()
        )

        if not callable(
            getattr(self.backend, "transact_records", None)
        ):
            raise RuntimeError(
                "Atomic Data Engine transaction support required"
            )

        self.project_root = (
            project_root
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        ).resolve()

        self.dispatcher = (
            dispatcher
            if dispatcher is not None
            else dispatch_coding_agent
        )

        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = None
        self.execution_lock = None

    @property
    def running(self) -> bool:
        return (
            self.thread is not None
            and self.thread.is_alive()
            and not self.stop_event.is_set()
        )

    def submit(
        self,
        *,
        request: str,
        workspace: str,
        target_files: list[str],
    ) -> dict:
        if not request.strip():
            raise ValueError("Coding request is empty")

        if not target_files:
            raise ValueError("Target files are required")

        job = {
            "execution_id": str(uuid4()),
            "request": request,
            "request_sha256": digest(request),
            "workspace": workspace,
            "target_files": list(target_files),
            "action": "coding_agent.execute",
            "created_at": utc_now(),
        }

        def transaction(records):
            append_event(records, JOB_TYPE, job)
            return {
                "execution_id": job["execution_id"],
                "status": "queued",
                "recorded": True,
                "coding_executed": False,
                "engineering_verified": False,
            }

        result = self.backend.transact_records(transaction)
        self.wake_event.set()
        return result

    def status(self, execution_id: str) -> dict:
        jobs, states = job_snapshot(
            self.backend.get_all_records()
        )

        if execution_id not in jobs:
            raise ValueError("Unknown execution identifier")

        state = states.get(execution_id, {})

        return {
            "execution_id": execution_id,
            "status": state.get("status", "queued"),
            "recorded": True,
            "coding_executed": state.get(
                "coding_executed", False
            ),
            "agent_execution_success": state.get(
                "agent_execution_success", False
            ),
            "engineering_verified": False,
            "exit_code": state.get("exit_code"),
            "audit_dir": state.get("audit_dir"),
            "result_sha256": state.get("result_sha256"),
            "error": state.get("error"),
        }

    def claim_next(self) -> dict | None:
        """Claim a queued job through one Data Engine transaction."""

        def transaction(records):
            jobs, states = job_snapshot(records)

            blocked_workspaces = {
                jobs[execution_id]["workspace"]
                for execution_id, event in states.items()
                if event["status"] in (
                    "running",
                    "interrupted",
                )
            }

            for execution_id, job in jobs.items():
                current = states.get(execution_id, {})
                status = current.get("status", "queued")

                if status != "queued":
                    continue

                if job["workspace"] in blocked_workspaces:
                    continue

                event = {
                    "execution_id": execution_id,
                    "status": "running",
                    "claimed_at": utc_now(),
                    "worker_pid": os.getpid(),
                    "coding_executed": False,
                    "engineering_verified": False,
                }

                append_event(records, STATE_TYPE, event)
                return dict(job)

            return None

        return self.backend.transact_records(transaction)

    def finish(
        self,
        execution_id: str,
        *,
        result: dict | None,
        error: str | None = None,
    ) -> dict:
        if result is not None and not isinstance(result, dict):
            raise TypeError("Invalid Aider result")

        succeeded = (
            isinstance(result, dict)
            and result.get("agent_execution_success") is True
            and type(result.get("exit_code")) is int
            and result["exit_code"] == 0
            and error is None
        )

        result_digest = None

        if result is not None:
            serialized = json.dumps(
                result,
                sort_keys=True,
                default=str,
            )
            result_digest = digest(serialized)

        event = {
            "execution_id": execution_id,
            "status": "completed" if succeeded else "failed",
            "finished_at": utc_now(),
            "coding_executed": result is not None,
            "agent_execution_success": succeeded,
            "engineering_verified": False,
            "exit_code": (
                result.get("exit_code")
                if result is not None
                else None
            ),
            "audit_dir": (
                result.get("audit_dir")
                if result is not None
                else None
            ),
            "result_sha256": result_digest,
            "error": error or (
                result.get("error")
                if result is not None
                else "Coding agent unavailable"
            ),
        }

        def transaction(records):
            jobs, states = job_snapshot(records)

            if execution_id not in jobs:
                raise RuntimeError("Unknown coding job")

            previous = states.get(execution_id, {})

            if previous.get("status") != "running":
                raise RuntimeError(
                    "Job is not in the running state"
                )

            append_event(records, STATE_TYPE, event)
            return event

        return self.backend.transact_records(transaction)

    def reconcile_interrupted(self) -> list[str]:
        """Do not replay work that may already have changed files."""

        def transaction(records):
            jobs, states = job_snapshot(records)
            interrupted = []

            for execution_id, event in states.items():
                if event["status"] != "running":
                    continue

                append_event(
                    records,
                    STATE_TYPE,
                    {
                        "execution_id": execution_id,
                        "status": "interrupted",
                        "interrupted_at": utc_now(),
                        "previous_worker_pid": event.get(
                            "worker_pid"
                        ),
                        "coding_executed": False,
                        "engineering_verified": False,
                        "error": (
                            "Execution interrupted; "
                            "workspace requires reconciliation"
                        ),
                    },
                )

                interrupted.append(execution_id)

            return interrupted

        return self.backend.transact_records(transaction)

    def execute(self, job: dict) -> None:
        execution_id = job["execution_id"]

        try:
            result = self.dispatcher(
                project_root=self.project_root,
                workspace=Path(job["workspace"]),
                request=job["request"],
                target_files=job["target_files"],
            )

            self.finish(
                execution_id,
                result=result,
            )

        except Exception as exc:
            try:
                self.finish(
                    execution_id,
                    result=None,
                    error=(
                        f"{type(exc).__name__}: {exc}"
                    ),
                )
            except Exception:
                traceback.print_exc()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                job = self.claim_next()

                if job is not None:
                    self.execute(job)
                    continue

            except Exception:
                traceback.print_exc()

            self.wake_event.wait(timeout=1.0)
            self.wake_event.clear()

    def start(self) -> None:
        if self.running:
            raise RuntimeError(
                "Coding job coordinator already running"
            )

        # Only one coordinator for the configured Data Engine.
        # This prevents separate service instances from
        # reconciling one another's live executions.
        lock_path = Path(
            str(self.backend.data_file)
            + ".coding-worker.lock"
        )

        self.execution_lock = open(
            lock_path,
            "a+",
            encoding="utf-8",
        )

        try:
            fcntl.flock(
                self.execution_lock.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )

            self.reconcile_interrupted()

            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._run,
                name="dataworc-coding-dispatcher",
                daemon=True,
            )
            self.thread.start()

        except Exception:
            self.execution_lock.close()
            self.execution_lock = None
            raise

    def stop(self) -> None:
        """
        Stop accepting new work and finish the active dispatch.

        Keep the coordinator lock until the execution thread
        has finished. Do not allow another coordinator to claim
        jobs while this process is still executing Aider.
        """
        self.stop_event.set()
        self.wake_event.set()

        thread = self.thread

        if thread is not None and thread.is_alive():
            if thread is threading.current_thread():
                raise RuntimeError(
                    "Coordinator cannot join itself"
                )

            thread.join()

        self.thread = None

        if self.execution_lock is not None:
            try:
                fcntl.flock(
                    self.execution_lock.fileno(),
                    fcntl.LOCK_UN,
                )
            finally:
                self.execution_lock.close()
                self.execution_lock = None
