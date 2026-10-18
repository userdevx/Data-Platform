from __future__ import annotations

import subprocess
from pathlib import Path

from engine.sandbox.manager import SandboxManager
from engine.sandbox.models import (
    IsolationClass,
    ResourceLimits,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)


def _gvisor_leftovers() -> list[str]:
    completed = subprocess.run(
        [
            "/usr/bin/docker",
            "ps",
            "-a",
            "--filter",
            "name=dataworc-gvisor-",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return [
        line
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def _podman_leftovers() -> list[str]:
    completed = subprocess.run(
        [
            "/usr/bin/podman",
            "ps",
            "-a",
            "--filter",
            "name=dataworc-sandbox-",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return [
        line
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def _incus_leftovers() -> list[str]:
    completed = subprocess.run(
        [
            "/usr/bin/incus",
            "list",
            "--format",
            "csv",
            "-c",
            "n",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return [
        line
        for line in completed.stdout.splitlines()
        if line.startswith("dataworc-sandbox-")
    ]


def test_manager_real_host_os_execution() -> None:
    manager = SandboxManager()

    request = SandboxRequest(
        workload_type=WorkloadType.TEST,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "sh",
            "-c",
            """
echo MANAGER_PODMAN_OK
uname -s
grep "^CapEff:" /proc/self/status
""",
        ),
        limits=ResourceLimits(
            cpu_count=0.5,
            memory_mb=256,
            timeout_seconds=10,
            pids=64,
        ),
    )

    result = manager.execute(request)

    print(result.stdout)

    assert result.runtime_kind == RuntimeKind.PODMAN
    assert result.isolation_class == IsolationClass.HOST_OS
    assert result.exit_code == 0
    assert result.timed_out is False

    assert "MANAGER_PODMAN_OK" in result.stdout
    assert "Linux" in result.stdout
    assert "CapEff:\t0000000000000000" in result.stdout

    assert _podman_leftovers() == []

    print("MANAGER_HOST_OS_OK")


def test_manager_real_kernel_emulation_execution() -> None:
    manager = SandboxManager()

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=(
            "sh",
            "-c",
            """
echo MANAGER_GVISOR_OK
uname -r
ip addr show
grep "^CapEff:" /proc/self/status
""",
        ),
        limits=ResourceLimits(
            cpu_count=0.5,
            memory_mb=256,
            timeout_seconds=10,
            pids=64,
        ),
    )

    result = manager.execute(request)

    print(result.stdout)

    assert result.runtime_kind == RuntimeKind.GVISOR
    assert (
        result.isolation_class
        == IsolationClass.KERNEL_EMULATION
    )
    assert result.exit_code == 0
    assert result.timed_out is False

    assert "MANAGER_GVISOR_OK" in result.stdout
    assert "-gvisor" in result.stdout
    assert "127.0.0.1" in result.stdout
    assert "eth0" not in result.stdout
    assert "CapEff:\t0000000000000000" in result.stdout

    assert _gvisor_leftovers() == []

    print("MANAGER_KERNEL_EMULATION_OK")


def _firecracker_processes() -> str:
    completed = subprocess.run(
        ["pgrep", "-af", "firecracker --id dataworc-fc-"],
        capture_output=True,
        text=True,
        check=False,
    )

    return (
        completed.stdout.strip()
        if completed.returncode == 0
        else ""
    )


def test_manager_real_firecracker_execution() -> None:
    manager = SandboxManager()

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.UNTRUSTED,
        command=(
            "/bin/sh",
            "-c",
            "echo MANAGER_FIRECRACKER_OK; "
            "systemd-detect-virt || true; "
            "nproc",
        ),
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=2,
            memory_mb=512,
            timeout_seconds=30,
            pids=32,
        ),
    )

    result = manager.execute(request)

    print(result.stdout)

    assert result.runtime_kind == RuntimeKind.FIRECRACKER
    assert result.isolation_class == IsolationClass.HARDWARE
    assert result.exit_code == 0
    assert result.timed_out is False

    lines = [line.strip() for line in result.stdout.splitlines()]
    start = lines.index("MANAGER_FIRECRACKER_OK")

    assert lines[start + 1] == "kvm"
    assert lines[start + 2] == "2"

    assert _firecracker_processes() == ""

    print("MANAGER_FIRECRACKER_OK")


def test_manager_real_hardware_workspace_uses_incus_vm(
    tmp_path: Path,
) -> None:
    manager = SandboxManager()

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.LIMITED,
        command=(
            "sh",
            "-c",
            """
echo MANAGER_INCUS_VM_OK
systemd-detect-virt
nproc
uname -r
ip addr show
""",
        ),
        # Firecracker cannot transfer a host workspace, so the
        # selector must fall back to the next hardware runtime.
        working_directory=tmp_path,
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=2,
            memory_mb=512,
            timeout_seconds=60,
            pids=64,
        ),
    )

    result = manager.execute(request)

    print(result.stdout)

    assert result.runtime_kind == RuntimeKind.INCUS_VM
    assert result.isolation_class == IsolationClass.HARDWARE
    assert result.exit_code == 0
    assert result.timed_out is False

    assert "MANAGER_INCUS_VM_OK" in result.stdout
    assert "kvm" in result.stdout
    assert "127.0.0.1" in result.stdout

    assert _incus_leftovers() == []

    print("MANAGER_HARDWARE_OK")


def test_manager_real_gvisor_timeout_cleanup() -> None:
    manager = SandboxManager()

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=(
            "sh",
            "-c",
            """
echo MANAGER_TIMEOUT_STARTED
sleep 30
echo SHOULD_NOT_COMPLETE
""",
        ),
        limits=ResourceLimits(
            cpu_count=0.25,
            memory_mb=128,
            timeout_seconds=3,
            pids=32,
        ),
    )

    result = manager.execute(request)

    print(
        f"runtime={result.runtime_kind.value}\n"
        f"exit_code={result.exit_code}\n"
        f"timed_out={result.timed_out}\n"
        f"duration={result.duration_seconds}"
    )

    assert result.runtime_kind == RuntimeKind.GVISOR
    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.duration_seconds >= 3
    assert result.duration_seconds < 6
    assert "SHOULD_NOT_COMPLETE" not in result.stdout

    assert _gvisor_leftovers() == []

    print("MANAGER_TIMEOUT_CLEANUP_OK")
