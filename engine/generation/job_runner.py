"""Detached generation job runner."""

from __future__ import annotations

import fcntl
import json
import os
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from .bindings import build_job_record_store, build_worker_command, PROJECT_ROOT
from .budget import ExecutionBudget
from .models import (
    FailureReason,
    GenerationJob,
    JobState,
    artifact_record,
)
from .runner import CompletedRun, run_bounded
from .service import (
    RUNNER_PID_DIRECTORY,
    SLOT_LOCK_PATH,
    job_from_spool,
)
from .store import JobRecordStore, publish


HEARTBEAT_INTERVAL_SECONDS = 20
SLOT_WAIT_TIMEOUT_SECONDS = 1800
DEFAULT_JOB_TIMEOUT_SECONDS = 1800


class SlotBusyError(RuntimeError):
    pass


def _acquire_slot(lock_path: Path, timeout_seconds: int):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w")
    deadline = time.monotonic() + timeout_seconds

    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError:
            if time.monotonic() >= deadline:
                handle.close()
                raise SlotBusyError(
                    "The generation slot did not become available within "
                    f"{timeout_seconds} seconds."
                )

            time.sleep(2)


def _was_cancelled(
    store: JobRecordStore,
    job_id: str,
) -> bool:
    return any(
        record.get(
            "value",
            {},
        ).get(
            "state"
        )
        == JobState.CANCELLED.value
        for record
        in store.job_records(
            job_id
        )
    )


class Heartbeat:
    def __init__(
        self,
        *,
        store: JobRecordStore,
        job: GenerationJob,
        interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self._store = store
        self._job = job
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            if _was_cancelled(
                self._store,
                self._job.job_id,
            ):
                return

            beating = replace(
                self._job,
                heartbeat_at=_utc_now(),
            )

            try:
                publish(
                    self._store,
                    beating,
                )
            except Exception:
                pass

    def __enter__(self) -> "Heartbeat":
        self._thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=self._interval + 5)


def _utc_now() -> str:
    from .models import utc_now

    return utc_now()


def _classify_failure(
    run: CompletedRun,
    *,
    budget: ExecutionBudget,
) -> FailureReason:
    if run.timed_out:
        return FailureReason.TIMEOUT

    signal_number = run.killed_by_signal

    if signal_number == 9 and budget.enforced:
        return FailureReason.BUDGET_EXCEEDED

    if signal_number is not None:
        return FailureReason.WORKER_ERROR

    payload = run.payload or {}
    reported = str(payload.get("failure_reason", "")).strip()

    if reported:
        try:
            return FailureReason(reported)
        except ValueError:
            pass

    return FailureReason.GENERATION


def _relative_to_root(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return path


def execute(job: GenerationJob, *, store: JobRecordStore) -> GenerationJob:
    if _was_cancelled(
        store,
        job.job_id,
    ):
        return job.transition(
            JobState.CANCELLED,
            reason=FailureReason.USER,
        )

    budget = ExecutionBudget(**job.budget)
    timeout_seconds = int(
        job.arguments.get("timeout_seconds", DEFAULT_JOB_TIMEOUT_SECONDS)
    )

    try:
        command = build_worker_command(job)
    except (ValueError, NotImplementedError) as error:
        job = job.transition(
            JobState.FAILED,
            reason=FailureReason.NO_CAPABLE_MODEL,
        )
        job.arguments["failure_detail"] = str(error)
        return publish(store, job)

    job = job.transition(JobState.RUNNING, heartbeat_at=_utc_now())
    publish(store, job)

    with Heartbeat(store=store, job=job):
        run = run_bounded(
            command,
            budget=budget,
            project_root=PROJECT_ROOT,
            timeout_seconds=timeout_seconds,
            unit_name=f"dp-generation-{job.job_id}",
        )

    job = replace(
        job,
        duration_ms=run.duration_ms,
        memory_peak_bytes=run.memory_peak_bytes,
        heartbeat_at=_utc_now(),
    )

    if _was_cancelled(
        store,
        job.job_id,
    ):
        return job.transition(
            JobState.CANCELLED,
            reason=FailureReason.USER,
        )

    payload = run.payload or {}
    succeeded = (
        run.returncode == 0
        and str(payload.get("status", "")) == "success"
    )

    if not succeeded:
        reason = _classify_failure(run, budget=budget)
        job = job.transition(JobState.FAILED, reason=reason)
        job.arguments["failure_detail"] = (
            run.stderr.strip()[-4000:] or f"exit {run.returncode}"
        )
        return publish(store, job)

    validation = payload.get("validation") or {}

    if not validation.get("non_degenerate", False):
        job = job.transition(JobState.FAILED, reason=FailureReason.VALIDATION)
        job.arguments["failure_detail"] = json.dumps(validation)
        return publish(store, job)

    artifact_id = str(uuid4())

    store.append(
        artifact_record(
            job,
            artifact_id=artifact_id,
            relative_path=_relative_to_root(str(payload.get("output_path", ""))),
            sha256=str(payload.get("sha256", "")),
            mime_type=str(payload.get("mime_type", "image/png")),
            validation=validation,
            pipeline_class=str(payload.get("pipeline_class", "")),
            runtime_format=str(payload.get("runtime_format", "")),
            device=str(payload.get("device", "")),
            dtype=str(payload.get("dtype", "")),
            source_artifact_sha256=str(payload.get("source_artifact_sha256", "")),
            source_dimensions=payload.get("source_dimensions"),
            working_dimensions=payload.get("working_dimensions"),
        )
    )

    job = job.transition(JobState.SUCCEEDED, artifact_id=artifact_id)
    return publish(store, job)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m engine.generation.job_runner <spool.json>")
        return 2

    spool = Path(argv[1])
    job = job_from_spool(spool)
    store = build_job_record_store()

    pid_directory = (
        PROJECT_ROOT
        / RUNNER_PID_DIRECTORY
    )

    pid_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    pid_path = (
        pid_directory
        / f"{job.job_id}.pid"
    )

    pid_path.write_text(
        str(
            os.getpid()
        ),
        encoding="utf-8",
    )

    handle = None

    try:
        if _was_cancelled(
            store,
            job.job_id,
        ):
            return 1

        lock_path = (
            PROJECT_ROOT
            / SLOT_LOCK_PATH
        )

        try:
            handle = _acquire_slot(
                lock_path,
                SLOT_WAIT_TIMEOUT_SECONDS,
            )
        except SlotBusyError as error:
            if _was_cancelled(
                store,
                job.job_id,
            ):
                return 1

            job = job.transition(
                JobState.FAILED,
                reason=FailureReason.TIMEOUT,
            )

            job.arguments[
                "failure_detail"
            ] = str(
                error
            )

            publish(
                store,
                job,
            )

            return 1

        if _was_cancelled(
            store,
            job.job_id,
        ):
            return 1

        try:
            finished = execute(
                job,
                store=store,
            )
        except Exception as error:
            if _was_cancelled(
                store,
                job.job_id,
            ):
                return 1

            job = job.transition(
                JobState.FAILED,
                reason=(
                    FailureReason
                    .WORKER_ERROR
                ),
            )

            job.arguments[
                "failure_detail"
            ] = repr(
                error
            )

            publish(
                store,
                job,
            )

            return 1

        return (
            0
            if finished.state
            is JobState.SUCCEEDED
            else 1
        )

    finally:
        if handle is not None:
            fcntl.flock(
                handle,
                fcntl.LOCK_UN,
            )

            handle.close()

        pid_path.unlink(
            missing_ok=True
        )

        spool.unlink(
            missing_ok=True
        )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
