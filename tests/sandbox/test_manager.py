from __future__ import annotations

from engine.sandbox import manager
from engine.sandbox.manager import SandboxManager
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
    SandboxRequest,
    SandboxResult,
    SandboxSelection,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.base import SandboxRuntime


class FakeRuntime(SandboxRuntime):
    def execute(
        self,
        request: SandboxRequest,
    ) -> SandboxResult:
        return SandboxResult(
            runtime_kind=RuntimeKind.PODMAN,
            isolation_class=IsolationClass.HOST_OS,
            command=tuple(request.command),
            exit_code=0,
            stdout="FAKE_RUNTIME_OK\n",
            stderr="",
            timed_out=False,
            duration_seconds=0.01,
        )


def test_manager_executes_selected_runtime(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        manager,
        "select_runtime",
        lambda request: SandboxSelection(
            isolation_class=IsolationClass.HOST_OS,
            runtime_kind=RuntimeKind.PODMAN,
            reason="test selection",
        ),
    )

    sandbox_manager = SandboxManager(
        runtime_factories={
            RuntimeKind.PODMAN: FakeRuntime,
        }
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("echo", "ok"),
    )

    result = sandbox_manager.execute(request)

    assert result.exit_code == 0
    assert result.runtime_kind == RuntimeKind.PODMAN
    assert result.stdout == "FAKE_RUNTIME_OK\n"
