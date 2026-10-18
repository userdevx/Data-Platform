from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from uuid import uuid4


class LifecycleError(RuntimeError):
    pass


class ExecutionState(str, Enum):
    CREATED = "created"
    VALIDATED = "validated"
    PREPARING = "preparing"
    RUNNING = "running"

    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    CLEANED = "cleaned"


_TERMINAL_EXECUTION_STATES = {
    ExecutionState.FINISHED,
    ExecutionState.FAILED,
    ExecutionState.CANCELLED,
    ExecutionState.TIMED_OUT,
}


_ALLOWED: dict[
    ExecutionState,
    set[ExecutionState],
] = {
    ExecutionState.CREATED: {
        ExecutionState.VALIDATED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.VALIDATED: {
        ExecutionState.PREPARING,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
    },
    ExecutionState.PREPARING: {
        ExecutionState.RUNNING,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
        ExecutionState.TIMED_OUT,
    },
    ExecutionState.RUNNING: {
        ExecutionState.FINISHED,
        ExecutionState.FAILED,
        ExecutionState.CANCELLED,
        ExecutionState.TIMED_OUT,
    },
    ExecutionState.FINISHED: {
        ExecutionState.CLEANED,
    },
    ExecutionState.FAILED: {
        ExecutionState.CLEANED,
    },
    ExecutionState.CANCELLED: {
        ExecutionState.CLEANED,
    },
    ExecutionState.TIMED_OUT: {
        ExecutionState.CLEANED,
    },
    ExecutionState.CLEANED: set(),
}


@dataclass(slots=True)
class ExecutionRecord:
    execution_id: str
    state: ExecutionState
    created_at_monotonic: float
    updated_at_monotonic: float

    cleanup_succeeded: bool | None = None
    cleanup_error: str | None = None


class ExecutionLifecycle:
    def create(self) -> ExecutionRecord:
        now = monotonic()

        return ExecutionRecord(
            execution_id=str(uuid4()),
            state=ExecutionState.CREATED,
            created_at_monotonic=now,
            updated_at_monotonic=now,
        )

    def transition(
        self,
        record: ExecutionRecord,
        target: ExecutionState,
    ) -> None:
        allowed = _ALLOWED[record.state]

        if target not in allowed:
            raise LifecycleError(
                "invalid lifecycle transition: "
                f"{record.state.value} -> "
                f"{target.value}"
            )

        record.state = target
        record.updated_at_monotonic = monotonic()

    def mark_cleanup_succeeded(
        self,
        record: ExecutionRecord,
    ) -> None:
        if record.state not in _TERMINAL_EXECUTION_STATES:
            raise LifecycleError(
                "cleanup can only complete after an "
                "execution terminal state"
            )

        record.cleanup_succeeded = True
        record.cleanup_error = None

        self.transition(
            record,
            ExecutionState.CLEANED,
        )

    def mark_cleanup_failed(
        self,
        record: ExecutionRecord,
        error: BaseException,
    ) -> None:
        if record.state not in _TERMINAL_EXECUTION_STATES:
            raise LifecycleError(
                "cleanup can only fail after an "
                "execution terminal state"
            )

        record.cleanup_succeeded = False
        record.cleanup_error = (
            f"{type(error).__name__}: {error}"
        )

        # Deliberately do not transition to CLEANED.
        # Persistent lease/recovery state must remain discoverable.
