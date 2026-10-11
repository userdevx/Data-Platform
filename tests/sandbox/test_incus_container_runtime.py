from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.incus_container import (
    IncusContainerRuntime,
)


def make_request(
    *,
    network_enabled: bool = False,
    working_directory: Path | None = None,
    writable_workspace: bool = False,
) -> SandboxRequest:
    return SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("sh", "-c", "echo INCUS_RUNTIME_OK"),
        network_enabled=network_enabled,
        working_directory=working_directory,
        writable_workspace=writable_workspace,
        limits=ResourceLimits(
            cpu_count=0.5,
            memory_mb=256,
            timeout_seconds=5,
            pids=64,
        ),
    )


def test_remote_image_reference_is_rejected() -> None:
    with pytest.raises(ValueError):
        IncusContainerRuntime(
            image="images:ubuntu/24.04",
        )


def test_cpu_allowance_is_hard_quota() -> None:
    runtime = IncusContainerRuntime()

    assert runtime._cpu_allowance(0.5) == "50ms/100ms"
    assert runtime._cpu_allowance(1.0) == "100ms/100ms"


def test_launch_command_is_ephemeral_and_networkless_by_default() -> None:
    runtime = IncusContainerRuntime()
    request = make_request()

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-test",
        request,
    )

    assert command[:4] == [
        "/usr/bin/incus",
        "launch",
        "dataworc-sandbox-ubuntu-24.04",
        "sandbox-test",
    ]

    assert "--ephemeral" in command
    assert "--no-profiles" in command
    assert "--storage" in command
    assert "default" in command

    assert "limits.cpu.allowance=50ms/100ms" in command
    assert "limits.memory=256MiB" in command
    assert "limits.memory.enforce=hard" in command
    assert "limits.processes=64" in command

    assert "--network" not in command


def test_network_is_added_only_when_requested() -> None:
    runtime = IncusContainerRuntime()

    request = make_request(
        network_enabled=True,
    )

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-test",
        request,
    )

    network_index = command.index("--network")

    assert command[network_index + 1] == "incusbr0"


def test_workspace_is_read_only_by_default(
    tmp_path: Path,
) -> None:
    runtime = IncusContainerRuntime()

    request = make_request(
        working_directory=tmp_path,
    )

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-test",
        request,
    )

    device_index = command.index("--device")
    device = command[device_index + 1]

    assert f"source={tmp_path.resolve()}" in device
    assert "path=/workspace" in device
    assert "readonly=true" in device


def test_workspace_can_be_explicitly_writable(
    tmp_path: Path,
) -> None:
    runtime = IncusContainerRuntime()

    request = make_request(
        working_directory=tmp_path,
        writable_workspace=True,
    )

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-test",
        request,
    )

    device_index = command.index("--device")
    device = command[device_index + 1]

    assert "readonly=false" in device


def test_missing_workspace_is_rejected(
    tmp_path: Path,
) -> None:
    runtime = IncusContainerRuntime()

    missing = tmp_path / "missing"

    request = make_request(
        working_directory=missing,
    )

    with pytest.raises(FileNotFoundError):
        runtime._build_launch_command(
            Path("/usr/bin/incus"),
            "sandbox-test",
            request,
        )


def test_exec_command_passes_environment() -> None:
    runtime = IncusContainerRuntime()

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "sh",
            "-c",
            'printf %s "$VALUE"',
        ),
        environment={
            "VALUE": "sandbox-value",
        },
    )

    command = runtime._build_exec_command(
        Path("/usr/bin/incus"),
        "sandbox-test",
        request,
    )

    assert command == [
        "/usr/bin/incus",
        "exec",
        "sandbox-test",
        "--force-noninteractive",
        "--env",
        "VALUE=sandbox-value",
        "--",
        "sh",
        "-c",
        'printf %s "$VALUE"',
    ]


@patch(
    "engine.sandbox.runtime.incus_container."
    "discover_incus_container"
)
@patch(
    "engine.sandbox.runtime.incus_container."
    "subprocess.run"
)
def test_execute_stops_ephemeral_instance_after_workload(
    run_mock,
    discover_mock,
) -> None:
    discover_mock.return_value.available = True
    discover_mock.return_value.executable = Path(
        "/usr/bin/incus"
    )
    discover_mock.return_value.reason = None

    run_mock.side_effect = [
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="image",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="launched",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="INCUS_RUNTIME_OK\n",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        ),
    ]

    result = IncusContainerRuntime().execute(
        make_request()
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.stdout == "INCUS_RUNTIME_OK\n"

    cleanup_command = run_mock.call_args_list[-1].args[0]

    assert cleanup_command[0] == "/usr/bin/incus"
    assert cleanup_command[1] == "stop"
    assert cleanup_command[2].startswith(
        "dataworc-sandbox-"
    )
    assert cleanup_command[3] == "--force"
