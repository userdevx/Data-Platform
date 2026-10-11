from __future__ import annotations

from pathlib import Path

import pytest

from engine.sandbox.models import (
    IsolationClass,
    ResourceLimits,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.podman import PodmanRuntime


def test_build_command_contains_security_controls() -> None:
    runtime = PodmanRuntime(
        image="docker.io/library/alpine:latest",
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("sh", "-c", "echo ok"),
        limits=ResourceLimits(
            cpu_count=0.5,
            memory_mb=256,
            timeout_seconds=3,
            pids=64,
        ),
    )

    command = runtime._build_command(request)

    assert "--rm" in command
    assert "--timeout=3" in command
    assert "--network" in command
    assert "none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert "--memory=256m" in command
    assert "--cpus=0.5" in command
    assert "--pids-limit=64" in command
    assert "--tmpfs" in command
    assert "/tmp:rw,noexec,nosuid,size=64m" in command


def test_network_can_be_enabled_explicitly() -> None:
    runtime = PodmanRuntime(
        image="docker.io/library/alpine:latest",
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
        network_enabled=True,
    )

    command = runtime._build_command(request)

    assert "--network" not in command


def test_missing_workspace_is_rejected(tmp_path: Path) -> None:
    runtime = PodmanRuntime(
        image="docker.io/library/alpine:latest",
    )

    missing = tmp_path / "missing"

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
        working_directory=missing,
    )

    with pytest.raises(FileNotFoundError):
        runtime._build_command(request)


def test_workspace_is_read_only_by_default(
    tmp_path: Path,
) -> None:
    runtime = PodmanRuntime(
        image="docker.io/library/alpine:latest",
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
        working_directory=tmp_path,
    )

    command = runtime._build_command(request)

    volume_index = command.index("--volume") + 1
    volume = command[volume_index]

    assert volume.endswith(":/workspace:ro,Z")


def test_runtime_executes_real_container() -> None:
    runtime = PodmanRuntime(
        image="docker.io/library/alpine:latest",
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "sh",
            "-c",
            "echo PODMAN_RUNTIME_OK",
        ),
        limits=ResourceLimits(
            cpu_count=0.5,
            memory_mb=128,
            timeout_seconds=10,
            pids=32,
        ),
    )

    result = runtime.execute(request)

    assert result.runtime_kind == RuntimeKind.PODMAN
    assert result.isolation_class == IsolationClass.HOST_OS
    assert result.exit_code == 0
    assert result.timed_out is False
    assert "PODMAN_RUNTIME_OK" in result.stdout


def test_runtime_enforces_native_timeout() -> None:
    runtime = PodmanRuntime(
        image="docker.io/library/alpine:latest",
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "sh",
            "-c",
            (
                "echo TIMEOUT_STARTED; "
                "sleep 30; "
                "echo SHOULD_NOT_PRINT"
            ),
        ),
        limits=ResourceLimits(
            cpu_count=0.25,
            memory_mb=128,
            timeout_seconds=3,
            pids=32,
        ),
    )

    result = runtime.execute(request)

    assert result.timed_out is True
    assert "TIMEOUT_STARTED" in result.stdout
    assert "SHOULD_NOT_PRINT" not in result.stdout
    assert result.duration_seconds < 10
