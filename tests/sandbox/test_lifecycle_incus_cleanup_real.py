from __future__ import annotations

import subprocess
from pathlib import Path

from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.incus_container import (
    IncusContainerRuntime,
)
from engine.sandbox.runtime.incus_vm import (
    IncusVmRuntime,
)


INCUS_TIMEOUT_SECONDS = 2
WORKLOAD_SLEEP_SECONDS = 30


def _incus_names(prefix: str) -> set[str]:
    completed = subprocess.run(
        [
            "incus",
            "list",
            "--format=csv",
            "-c",
            "n",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Unable to inspect real Incus instances: "
            + (
                completed.stderr.strip()
                or completed.stdout.strip()
                or f"exit={completed.returncode}"
            )
        )

    return {
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().startswith(prefix)
    }


def _request() -> SandboxRequest:
    return SandboxRequest(
        workload_type=WorkloadType.SCRIPT,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "/bin/sh",
            "-c",
            f"sleep {WORKLOAD_SLEEP_SECONDS}",
        ),
        network_enabled=False,
        limits=ResourceLimits(
            cpu_count=1.0,
            memory_mb=512,
            timeout_seconds=INCUS_TIMEOUT_SECONDS,
            pids=64,
        ),
    )


def _assert_no_new_instances(
    prefix: str,
    before: set[str],
) -> None:
    after = _incus_names(prefix)

    leaked = after - before

    assert not leaked, (
        "Incus sandbox resources survived cleanup: "
        f"{sorted(leaked)}"
    )


def test_real_incus_container_timeout_removes_instance() -> None:
    prefix = "dataworc-sandbox-"
    before = _incus_names(prefix)

    runtime = IncusContainerRuntime()

    result = runtime.execute(
        _request()
    )

    assert result.timed_out is True
    assert result.exit_code == 124

    _assert_no_new_instances(
        prefix,
        before,
    )

    print(
        "REAL_INCUS_CONTAINER_TIMEOUT_CLEANUP_OK"
    )


def test_real_incus_vm_timeout_removes_instance() -> None:
    prefix = "dataworc-vm-"
    before = _incus_names(prefix)

    runtime = IncusVmRuntime()

    result = runtime.execute(
        _request()
    )

    assert result.timed_out is True
    assert result.exit_code == 124

    _assert_no_new_instances(
        prefix,
        before,
    )

    print(
        "REAL_INCUS_VM_TIMEOUT_CLEANUP_OK"
    )
