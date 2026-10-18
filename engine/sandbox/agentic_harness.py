from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from engine.sandbox.lifecycle import (
    ExecutionLifecycle,
    ExecutionState,
    ResourcePolicy,
)


class SandboxExecutor(Protocol):
    def execute(self, request: object) -> Any:
        ...


@dataclass(frozen=True)
class AgenticExecution:
    execution_id: str
    result: Any


class AgenticHarnessSandbox:
    """Sandbox boundary consumed by the Agentic Harness.

    The Harness owns orchestration. It does not invoke Podman, gVisor,
    Incus, QEMU, Firecracker, or any concrete runtime directly.
    """

    def __init__(
        self,
        executor: SandboxExecutor,
        *,
        resource_policy: ResourcePolicy | None = None,
    ) -> None:
        self._executor = executor
        self._resource_policy = (
            resource_policy
            if resource_policy is not None
            else ResourcePolicy()
        )
        self._lifecycle = ExecutionLifecycle()

    def execute(self, request: object) -> AgenticExecution:
        record = self._lifecycle.create()

        try:
            self._resource_policy.validate(request)
            self._lifecycle.transition(
                record,
                ExecutionState.VALIDATED,
            )

            self._lifecycle.transition(
                record,
                ExecutionState.PREPARING,
            )

            self._lifecycle.transition(
                record,
                ExecutionState.RUNNING,
            )

            result = self._executor.execute(request)

            self._lifecycle.transition(
                record,
                ExecutionState.FINISHED,
            )

            return AgenticExecution(
                execution_id=record.execution_id,
                result=result,
            )

        except BaseException:
            if record.state not in {
                ExecutionState.FINISHED,
                ExecutionState.FAILED,
                ExecutionState.CLEANED,
            }:
                self._lifecycle.transition(
                    record,
                    ExecutionState.FAILED,
                )
            raise

        finally:
            if record.state in {
                ExecutionState.FINISHED,
                ExecutionState.FAILED,
            }:
                self._lifecycle.transition(
                    record,
                    ExecutionState.CLEANED,
                )
