from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.incus_container import IncusContainerRuntime
from engine.sandbox.runtime.incus_vm import IncusVmRuntime


_RUNTIMES = {
    "incus_container": IncusContainerRuntime,
    "incus_vm": IncusVmRuntime,
}


def _incus_leftovers() -> list[str]:
    completed = subprocess.run(
        ["/usr/bin/incus", "list", "--format", "csv", "-c", "n"],
        capture_output=True,
        text=True,
        check=True,
    )

    return [
        line
        for line in completed.stdout.splitlines()
        if line.startswith("dataworc-sandbox-")
    ]


def _workspace(tmp_path: Path) -> Path:
    # Incus shares the directory into the instance; a home-backed path
    # avoids private /tmp namespaces on the host.
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("incus-workspace-ok\n")
    return workspace


def _request(
    workspace: Path,
    script: str,
    *,
    writable: bool,
) -> SandboxRequest:
    return SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.LIMITED,
        command=("sh", "-c", script),
        working_directory=workspace,
        writable_workspace=writable,
        limits=ResourceLimits(
            cpu_count=1,
            memory_mb=512,
            timeout_seconds=60,
            pids=64,
        ),
    )


@pytest.mark.parametrize("runtime_name", sorted(_RUNTIMES))
def test_real_workspace_is_mounted_read_only(
    runtime_name: str,
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)

    result = _RUNTIMES[runtime_name]().execute(
        _request(
            workspace,
            "pwd; cat marker.txt; "
            "if touch created.txt 2>/dev/null; "
            "then echo WRITE_ALLOWED; else echo WRITE_REFUSED; fi",
            writable=False,
        )
    )

    print(result)

    assert result.exit_code == 0, result.stderr

    lines = result.stdout.splitlines()

    assert "/workspace" in lines
    assert "incus-workspace-ok" in lines
    assert "WRITE_REFUSED" in lines
    assert not (workspace / "created.txt").exists()

    assert _incus_leftovers() == []

    print(f"REAL_{runtime_name.upper()}_READ_ONLY_WORKSPACE_OK")


@pytest.mark.parametrize("runtime_name", sorted(_RUNTIMES))
def test_real_workspace_is_writable_when_requested(
    runtime_name: str,
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)

    result = _RUNTIMES[runtime_name]().execute(
        _request(
            workspace,
            "echo written-in-sandbox > created.txt && echo WRITE_OK",
            writable=True,
        )
    )

    print(result)

    assert result.exit_code == 0, result.stderr
    assert "WRITE_OK" in result.stdout
    assert (workspace / "created.txt").exists()

    assert _incus_leftovers() == []

    print(f"REAL_{runtime_name.upper()}_WRITABLE_WORKSPACE_OK")
