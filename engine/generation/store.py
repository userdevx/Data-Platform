"""Record store boundary for generation job lifecycle state."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Protocol

from .models import (
    CATEGORY_JOB_STATE,
    DATA_TYPE_JOB_STATUS,
    GenerationJob,
    JobState,
    TERMINAL_STATES,
    job_state_record,
)


class JobRecordStore(Protocol):
    def append(self, record: dict[str, Any]) -> None:
        """Persist one record envelope."""

    def job_records(self, job_id: str) -> list[dict[str, Any]]:
        """Return every job-state record for job_id, oldest first."""

    def open_jobs(self) -> list[dict[str, Any]]:
        """Return latest record for each non-terminal job."""

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        """Return latest record for a job with this key, if any."""


class DataEngineJobRecordStore:
    def __init__(
        self,
        *,
        append_record: Callable[[dict[str, Any]], None],
        query_records: Callable[[str, str], Iterable[dict[str, Any]]],
    ) -> None:
        self._append_record = append_record
        self._query_records = query_records

    def append(self, record: dict[str, Any]) -> None:
        self._append_record(record)

    def _all_job_records(self) -> list[dict[str, Any]]:
        return [
            record
            for record in self._query_records(
                CATEGORY_JOB_STATE,
                DATA_TYPE_JOB_STATUS,
            )
            if isinstance(record, dict)
        ]

    def job_records(self, job_id: str) -> list[dict[str, Any]]:
        return [
            record
            for record in self._all_job_records()
            if record.get("value", {}).get("job_id") == job_id
        ]

    def _latest_per_job(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}

        for record in self._all_job_records():
            job_id = record.get("value", {}).get("job_id")

            if isinstance(job_id, str) and job_id:
                latest[job_id] = record

        return latest

    def open_jobs(self) -> list[dict[str, Any]]:
        open_states = {
            state.value
            for state in JobState
            if state not in TERMINAL_STATES
        }

        return [
            record
            for record in self._latest_per_job().values()
            if record.get("value", {}).get("state") in open_states
        ]

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        matches = [
            record
            for record in self._latest_per_job().values()
            if record.get("value", {}).get("idempotency_key") == key
        ]

        if not matches:
            return None

        return max(
            matches,
            key=lambda record: record.get("value", {}).get("created_at", ""),
        )


class InMemoryJobRecordStore:
    """Test double. Not a runtime store."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def append(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    def _job_state_records(self) -> list[dict[str, Any]]:
        return [
            record
            for record in self.records
            if record.get("category") == CATEGORY_JOB_STATE
        ]

    def job_records(self, job_id: str) -> list[dict[str, Any]]:
        return [
            record
            for record in self._job_state_records()
            if record.get("value", {}).get("job_id") == job_id
        ]

    def _latest_per_job(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}

        for record in self._job_state_records():
            job_id = record.get("value", {}).get("job_id")

            if isinstance(job_id, str) and job_id:
                latest[job_id] = record

        return latest

    def open_jobs(self) -> list[dict[str, Any]]:
        open_states = {
            state.value
            for state in JobState
            if state not in TERMINAL_STATES
        }

        return [
            record
            for record in self._latest_per_job().values()
            if record.get("value", {}).get("state") in open_states
        ]

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        for record in reversed(list(self._latest_per_job().values())):
            if record.get("value", {}).get("idempotency_key") == key:
                return record

        return None


def publish(store: JobRecordStore, job: GenerationJob) -> GenerationJob:
    store.append(job_state_record(job))
    return job
