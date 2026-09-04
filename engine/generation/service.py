"""Generation job lifecycle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .budget import (
    ExecutionBudget,
    HardwareSnapshot,
    InsufficientResourcesError,
    current_budget,
)
from .pressure import read_pressure
from .models import (
    FailureReason,
    GenerationJob,
    GenerationProfile,
    JobState,
    SAFE_BASELINE,
    TERMINAL_STATES,
    build_idempotency_key,
    new_job,
    utc_now,
)
from .store import JobRecordStore, publish


DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 120
SPOOL_DIRECTORY = Path("var/generation/spool")
SLOT_LOCK_PATH = Path("var/generation/slot.lock")

JOB_RUNNER_MODULE = "engine.generation.job_runner"


class GenerationJobService:
    def __init__(
        self,
        *,
        store: JobRecordStore,
        project_root: Path,
        python_executable: str | Path | None = None,
        heartbeat_timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
        budget_provider: Callable[
            [], tuple[HardwareSnapshot, ExecutionBudget]
        ] = current_budget,
    ) -> None:
        self._store = store
        self._project_root = Path(project_root).resolve()
        self._python = str(python_executable or sys.executable)
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._budget_provider = budget_provider

    def submit(
        self,
        *,
        capability: str,
        prompt: str,
        model_id: str,
        profile: GenerationProfile | None = None,
        request_id: str = "",
        arguments: dict[str, Any] | None = None,
        detach: bool = True,
    ) -> GenerationJob:
        profile = profile or SAFE_BASELINE
        arguments = dict(arguments or {})

        existing = self._existing_job_for(
            capability=capability,
            prompt=prompt,
            model_id=model_id,
            profile=profile,
            arguments=arguments,
        )

        if existing is not None:
            return existing

        try:
            snapshot, budget = self._budget_provider()
        except InsufficientResourcesError as error:
            return self._reject(
                capability=capability,
                prompt=prompt,
                model_id=model_id,
                profile=profile,
                arguments=arguments,
                request_id=request_id,
                reason=FailureReason.INSUFFICIENT_RESOURCES,
                detail=str(error),
            )

        job = new_job(
            capability=capability,
            prompt=prompt,
            profile=profile,
            budget=budget.as_dict(),
            hardware={
                **snapshot.as_dict(),
                "pressure": read_pressure().as_dict(),
            },
            request_id=request_id,
            model_id=model_id,
            arguments=arguments,
        )

        publish(self._store, job)

        if detach:
            self._spawn_runner(job)

        return job

    def _existing_job_for(
        self,
        *,
        capability: str,
        prompt: str,
        model_id: str,
        profile: GenerationProfile,
        arguments: dict[str, Any],
    ) -> GenerationJob | None:
        key = build_idempotency_key(
            capability=capability,
            prompt=prompt,
            model_id=model_id,
            profile=profile,
            arguments=arguments,
        )

        record = self._store.find_by_idempotency_key(key)

        if record is None:
            return None

        value = record.get("value", {})

        if value.get("state") in {state.value for state in TERMINAL_STATES}:
            return None

        return job_from_record(record)

    def _reject(
        self,
        *,
        capability: str,
        prompt: str,
        model_id: str,
        profile: GenerationProfile,
        arguments: dict[str, Any],
        request_id: str,
        reason: FailureReason,
        detail: str,
    ) -> GenerationJob:
        job = new_job(
            capability=capability,
            prompt=prompt,
            profile=profile,
            budget={},
            hardware={},
            request_id=request_id,
            model_id=model_id,
            arguments=arguments,
        )

        job = job.transition(JobState.REJECTED, reason=reason)
        job.arguments["rejection_detail"] = detail

        return publish(self._store, job)

    def _spawn_runner(self, job: GenerationJob) -> None:
        spool = self._project_root / SPOOL_DIRECTORY
        spool.mkdir(parents=True, exist_ok=True)

        handle = spool / f"{job.job_id}.json"
        handle.write_text(
            json.dumps(job.as_dict(), sort_keys=True),
            encoding="utf-8",
        )

        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(self._project_root)

        subprocess.Popen(
            [self._python, "-m", JOB_RUNNER_MODULE, str(handle)],
            cwd=self._project_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def get(self, job_id: str) -> GenerationJob | None:
        records = self._store.job_records(job_id)

        if not records:
            return None

        return job_from_record(records[-1])

    def history(self, job_id: str) -> list[dict[str, Any]]:
        return [
            record.get("value", {})
            for record in self._store.job_records(job_id)
        ]

    def reap_stale_jobs(self, *, now: datetime | None = None) -> list[GenerationJob]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self._heartbeat_timeout_seconds)

        reaped: list[GenerationJob] = []

        for record in self._store.open_jobs():
            value = record.get("value", {})

            if value.get("state") != JobState.RUNNING.value:
                continue

            marker = value.get("heartbeat_at") or value.get("started_at")

            if not marker:
                continue

            try:
                seen_at = datetime.fromisoformat(marker)
            except ValueError:
                continue

            if seen_at.tzinfo is None:
                seen_at = seen_at.replace(tzinfo=timezone.utc)

            if seen_at > cutoff:
                continue

            job = job_from_record(record).transition(
                JobState.FAILED,
                reason=FailureReason.HEARTBEAT_LOST,
            )

            reaped.append(publish(self._store, job))

        return reaped


def job_from_record(record: dict[str, Any]) -> GenerationJob:
    value = record.get("value", {})
    resources = value.get("resources", {}) or {}

    return GenerationJob(
        job_id=str(value.get("job_id", "")),
        request_id=str(value.get("request_id", "")),
        capability=str(value.get("capability", "")),
        prompt="",
        profile=GenerationProfile(**(value.get("profile") or {})),
        budget=value.get("budget") or {},
        hardware=value.get("hardware") or {},
        idempotency_key=str(value.get("idempotency_key", "")),
        model_id=str(value.get("model_id", "")),
        state=JobState(str(value.get("state", JobState.QUEUED.value))),
        reason=value.get("reason"),
        artifact_id=value.get("artifact_id"),
        created_at=str(value.get("created_at") or utc_now()),
        started_at=value.get("started_at"),
        ended_at=value.get("ended_at"),
        heartbeat_at=value.get("heartbeat_at"),
        arguments=value.get("arguments") or {},
        memory_peak_bytes=resources.get("memory_peak_bytes"),
        duration_ms=resources.get("duration_ms"),
    )


def job_from_spool(path: Path) -> GenerationJob:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    return GenerationJob(
        job_id=payload["job_id"],
        request_id=payload["request_id"],
        capability=payload["capability"],
        prompt=payload["prompt"],
        profile=GenerationProfile(**payload["profile"]),
        budget=payload.get("budget") or {},
        hardware=payload.get("hardware") or {},
        idempotency_key=payload["idempotency_key"],
        model_id=payload.get("model_id", ""),
        state=JobState(payload.get("state", JobState.QUEUED.value)),
        arguments=payload.get("arguments") or {},
        created_at=payload.get("created_at") or utc_now(),
    )
