from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)
from typing import Any

from engine.sandbox.lifecycle.timeout import (
    ProcessOutcome,
)
from engine.sandbox.models import (
    SandboxRequest,
    SandboxResult,
)


@dataclass(frozen=True, slots=True)
class ExecutionRequestEvidence:
    workload_type: str
    trust_level: str
    command: tuple[str, ...]
    working_directory: str | None
    network_enabled: bool
    writable_workspace: bool
    requires_full_system: bool
    requires_vm_boundary: bool
    requires_kubernetes_runtime: bool
    environment_keys: tuple[str, ...]
    limits: dict[str, int | float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SandboxResultEvidence:
    runtime_kind: str
    isolation_class: str
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProcessOutcomeEvidence:
    argv: tuple[str, ...]
    pid: int
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    cancelled: bool
    duration_seconds: float
    stdout_truncated: bool
    stderr_truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def request_evidence(
    request: SandboxRequest,
) -> ExecutionRequestEvidence:
    if not isinstance(
        request,
        SandboxRequest,
    ):
        raise TypeError(
            "request must be a SandboxRequest"
        )

    return ExecutionRequestEvidence(
        workload_type=request.workload_type.value,
        trust_level=request.trust_level.value,
        command=tuple(
            str(part)
            for part in request.command
        ),
        working_directory=(
            str(request.working_directory)
            if request.working_directory is not None
            else None
        ),
        network_enabled=request.network_enabled,
        writable_workspace=request.writable_workspace,
        requires_full_system=request.requires_full_system,
        requires_vm_boundary=request.requires_vm_boundary,
        requires_kubernetes_runtime=(
            request.requires_kubernetes_runtime
        ),
        environment_keys=tuple(
            sorted(
                request.environment.keys()
            )
        ),
        limits={
            "cpu_count": request.limits.cpu_count,
            "memory_mb": request.limits.memory_mb,
            "timeout_seconds": request.limits.timeout_seconds,
            "pids": request.limits.pids,
        },
    )


def result_evidence(
    result: SandboxResult,
) -> SandboxResultEvidence:
    if not isinstance(
        result,
        SandboxResult,
    ):
        raise TypeError(
            "result must be a SandboxResult"
        )

    return SandboxResultEvidence(
        runtime_kind=result.runtime_kind.value,
        isolation_class=result.isolation_class.value,
        command=result.command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
        duration_seconds=result.duration_seconds,
    )


def process_outcome_evidence(
    outcome: ProcessOutcome,
) -> ProcessOutcomeEvidence:
    if not isinstance(
        outcome,
        ProcessOutcome,
    ):
        raise TypeError(
            "outcome must be a ProcessOutcome"
        )

    return ProcessOutcomeEvidence(
        argv=outcome.argv,
        pid=outcome.pid,
        exit_code=outcome.exit_code,
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        timed_out=outcome.timed_out,
        cancelled=outcome.cancelled,
        duration_seconds=outcome.duration_seconds,
        stdout_truncated=outcome.stdout_truncated,
        stderr_truncated=outcome.stderr_truncated,
    )
