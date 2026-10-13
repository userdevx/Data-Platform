from __future__ import annotations

import subprocess
from pathlib import Path

from engine.sandbox.models import (
    IsolationClass,
    ResourceLimits,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.qemu import QemuRuntime


def assert_no_qemu_residual() -> None:
    completed = subprocess.run(
        [
            "pgrep",
            "-af",
            "qemu-system.*dataworc-qemu-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0, (
        "Residual DataWorc QEMU process:\n"
        + completed.stdout
    )


def test_real_qemu_execution() -> None:
    image = Path(
        "engine/sandbox/images/qemu/"
        "ubuntu-24.04/provisioned.qcow2"
    )

    assert image.is_file()

    runtime = QemuRuntime(
        boot_timeout_seconds=90,
    )

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.LIMITED,
        command=[
            "/bin/sh",
            "-lc",
            (
                "printf 'QEMU_RUNTIME_OK\\n'; "
                "systemd-detect-virt; "
                "getconf _NPROCESSORS_ONLN; "
                "awk '/MemTotal/ {print $2}' "
                "/proc/meminfo; "
                "ls -1 /sys/class/net | sort"
            ),
        ],
        network_enabled=False,
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=1,
            memory_mb=512,
            timeout_seconds=20,
            pids=64,
        ),
    )

    result = runtime.execute(request)

    print(result.stdout)
    print(result.stderr)

    assert result.runtime_kind == RuntimeKind.QEMU_KVM
    assert (
        result.isolation_class
        == IsolationClass.HARDWARE
    )

    assert result.exit_code == 0
    assert result.timed_out is False

    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    assert "QEMU_RUNTIME_OK" in lines
    assert "kvm" in lines
    assert "1" in lines
    assert "lo" in lines

    assert_no_qemu_residual()

    print("REAL_QEMU_EXECUTION_OK")


def test_real_qemu_timeout_cleanup() -> None:
    runtime = QemuRuntime(
        boot_timeout_seconds=90,
    )

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.LIMITED,
        command=[
            "/bin/sh",
            "-lc",
            "sleep 30",
        ],
        network_enabled=False,
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=1,
            memory_mb=512,
            timeout_seconds=3,
            pids=32,
        ),
    )

    result = runtime.execute(request)

    print(f"runtime={result.runtime_kind.value}")
    print(f"exit_code={result.exit_code}")
    print(f"timed_out={result.timed_out}")
    print(
        f"duration={result.duration_seconds}"
    )

    assert result.runtime_kind == RuntimeKind.QEMU_KVM
    assert (
        result.isolation_class
        == IsolationClass.HARDWARE
    )

    assert result.exit_code == 124
    assert result.timed_out is True

    assert result.duration_seconds >= 3
    assert result.duration_seconds < 8

    assert_no_qemu_residual()

    print("REAL_QEMU_TIMEOUT_OK")
