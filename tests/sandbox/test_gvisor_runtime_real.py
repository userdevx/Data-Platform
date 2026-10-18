from __future__ import annotations

import subprocess

import pytest

from engine.sandbox.models import (
    IsolationClass,
    ResourceLimits,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.gvisor import (
    GVisorRuntime,
    GVisorRuntimeUnavailable,
)


def _gvisor_containers() -> list[str]:
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
        name
        for name in completed.stdout.splitlines()
        if name.strip()
    ]


def test_real_gvisor_execution() -> None:
    assert _gvisor_containers() == []

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=(
            "sh",
            "-c",
            """
echo GVISOR_RUNTIME_OK
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

    result = GVisorRuntime().execute(request)

    assert result.runtime_kind == RuntimeKind.GVISOR
    assert (
        result.isolation_class
        == IsolationClass.KERNEL_EMULATION
    )
    assert result.exit_code == 0
    assert result.timed_out is False

    assert "GVISOR_RUNTIME_OK" in result.stdout
    assert "-gvisor" in result.stdout
    assert "127.0.0.1" in result.stdout
    assert "eth0" not in result.stdout
    assert "CapEff:\t0000000000000000" in result.stdout

    assert "--runtime=runsc" in result.command
    assert "--pull=never" in result.command
    assert "--read-only" in result.command
    assert "--cap-drop=ALL" in result.command
    assert "--security-opt=no-new-privileges" in result.command
    assert "--memory=256m" in result.command
    assert "--cpus=0.5" in result.command
    assert "--pids-limit=64" in result.command

    assert _gvisor_containers() == []


def test_real_gvisor_timeout_cleanup() -> None:
    assert _gvisor_containers() == []

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=(
            "sh",
            "-c",
            """
echo GVISOR_TIMEOUT_STARTED
sleep 30
echo THIS_SHOULD_NOT_PRINT
""",
        ),
        limits=ResourceLimits(
            cpu_count=0.25,
            memory_mb=128,
            timeout_seconds=3,
            pids=32,
        ),
    )

    result = GVisorRuntime().execute(request)

    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.duration_seconds >= 3
    assert result.duration_seconds < 6
    assert "THIS_SHOULD_NOT_PRINT" not in result.stdout

    assert _gvisor_containers() == []


def test_real_gvisor_missing_image_fails_closed() -> None:
    runtime = GVisorRuntime(
        image="dataworc-gvisor-image-that-does-not-exist:test",
    )

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=("true",),
        limits=ResourceLimits(
            cpu_count=0.25,
            memory_mb=128,
            timeout_seconds=3,
            pids=32,
        ),
    )

    with pytest.raises(
        GVisorRuntimeUnavailable,
        match="Required local Docker image is unavailable",
    ):
        runtime.execute(request)

    assert _gvisor_containers() == []
