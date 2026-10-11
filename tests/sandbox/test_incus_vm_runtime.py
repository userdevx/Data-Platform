from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.sandbox.models import (
    IsolationClass,
    ResourceLimits,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.incus_vm import (
    IncusVmRuntime,
    IncusVmRuntimeUnavailable,
)


def make_request(
    *,
    cpu_count: float = 2.0,
    network_enabled: bool = False,
    working_directory: Path | None = None,
    writable_workspace: bool = False,
) -> SandboxRequest:
    return SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.TRUSTED,
        command=("sh", "-c", "echo INCUS_VM_RUNTIME_OK"),
        network_enabled=network_enabled,
        working_directory=working_directory,
        writable_workspace=writable_workspace,
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=cpu_count,
            memory_mb=512,
            timeout_seconds=10,
            pids=64,
        ),
    )


def test_remote_vm_image_reference_is_rejected() -> None:
    with pytest.raises(ValueError):
        IncusVmRuntime(
            image="images:ubuntu/24.04",
        )


def test_fractional_vcpu_request_is_rejected() -> None:
    runtime = IncusVmRuntime()

    with pytest.raises(
        ValueError,
        match="whole number",
    ):
        runtime._validate_request(
            make_request(cpu_count=0.5)
        )


def test_launch_command_creates_networkless_ephemeral_vm() -> None:
    runtime = IncusVmRuntime()

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-vm-test",
        make_request(),
    )

    assert command[:4] == [
        "/usr/bin/incus",
        "launch",
        "dataworc-sandbox-ubuntu-24.04-vm",
        "sandbox-vm-test",
    ]

    assert "--vm" in command
    assert "--ephemeral" in command
    assert "--no-profiles" in command
    assert "--storage" in command
    assert "default" in command
    assert "limits.cpu=2" in command
    assert "limits.memory=512MiB" in command

    assert "--network" not in command
    assert not any(
        "limits.processes" in item
        for item in command
    )


def test_network_is_added_only_when_requested() -> None:
    runtime = IncusVmRuntime()

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-vm-test",
        make_request(network_enabled=True),
    )

    index = command.index("--network")

    assert command[index + 1] == "incusbr0"


def test_vm_workspace_is_read_only_by_default(
    tmp_path: Path,
) -> None:
    runtime = IncusVmRuntime()

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-vm-test",
        make_request(
            working_directory=tmp_path,
        ),
    )

    index = command.index("--device")
    device = command[index + 1]

    assert f"source={tmp_path.resolve()}" in device
    assert "path=/workspace" in device
    assert "readonly=true" in device


def test_vm_workspace_can_be_writable(
    tmp_path: Path,
) -> None:
    runtime = IncusVmRuntime()

    command = runtime._build_launch_command(
        Path("/usr/bin/incus"),
        "sandbox-vm-test",
        make_request(
            working_directory=tmp_path,
            writable_workspace=True,
        ),
    )

    index = command.index("--device")

    assert (
        "readonly=false"
        in command[index + 1]
    )


def test_missing_vm_workspace_is_rejected(
    tmp_path: Path,
) -> None:
    runtime = IncusVmRuntime()

    with pytest.raises(FileNotFoundError):
        runtime._build_launch_command(
            Path("/usr/bin/incus"),
            "sandbox-vm-test",
            make_request(
                working_directory=(
                    tmp_path / "missing"
                ),
            ),
        )


def test_exec_uses_systemd_tasks_limit() -> None:
    runtime = IncusVmRuntime()

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "sh",
            "-c",
            'printf %s "$VALUE"',
        ),
        environment={
            "VALUE": "vm-value",
        },
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=2,
            memory_mb=512,
            timeout_seconds=10,
            pids=64,
        ),
    )

    command = runtime._build_exec_command(
        Path("/usr/bin/incus"),
        "sandbox-vm-test",
        request,
    )

    assert "systemd-run" in command
    assert "--property=TasksMax=64" in command
    assert "--setenv=VALUE=vm-value" in command

    separator = len(command) - 4

    assert command[separator:] == [
        "--",
        "sh",
        "-c",
        'printf %s "$VALUE"',
    ]


@patch(
    "engine.sandbox.runtime.incus_vm."
    "subprocess.run"
)
def test_non_vm_local_image_is_rejected(
    run_mock,
) -> None:
    run_mock.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="Type: container\n",
        stderr="",
    )

    with pytest.raises(
        IncusVmRuntimeUnavailable,
        match="not a virtual-machine image",
    ):
        IncusVmRuntime()._ensure_local_vm_image(
            Path("/usr/bin/incus")
        )


@patch(
    "engine.sandbox.runtime.incus_vm."
    "discover_incus_vm"
)
@patch(
    "engine.sandbox.runtime.incus_vm."
    "subprocess.run"
)
def test_execute_cleans_up_vm_after_success(
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
            stdout="Type: virtual-machine\n",
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
            stdout="",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="INCUS_VM_RUNTIME_OK\n",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        ),
    ]

    result = IncusVmRuntime().execute(
        make_request()
    )

    assert result.runtime_kind == RuntimeKind.INCUS_VM
    assert result.isolation_class == IsolationClass.HARDWARE
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.stdout == "INCUS_VM_RUNTIME_OK\n"

    cleanup = run_mock.call_args_list[-1].args[0]

    assert cleanup[0] == "/usr/bin/incus"
    assert cleanup[1] == "stop"
    assert cleanup[2].startswith(
        "dataworc-vm-"
    )
    assert cleanup[3] == "--force"
