from __future__ import annotations

import json

import subprocess
import time
from pathlib import Path
from uuid import uuid4

from engine.sandbox.discovery import discover_incus_vm
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
    SandboxRequest,
    SandboxResult,
)
from engine.sandbox.runtime.base import SandboxRuntime


class IncusVmRuntimeUnavailable(RuntimeError):
    pass


class IncusVmCleanupError(RuntimeError):
    pass


class IncusVmRuntime(SandboxRuntime):
    runtime_kind = RuntimeKind.INCUS_VM

    def __init__(
        self,
        image: str = "dataworc-sandbox-ubuntu-24.04-vm",
        storage_pool: str = "default",
        network: str = "incusbr0",
        provisioning_timeout_seconds: int = 180,
        agent_poll_interval_seconds: float = 1.0,
    ) -> None:
        if ":" in image:
            raise ValueError(
                "IncusVmRuntime requires a local image alias; "
                "remote image references are not allowed during execution"
            )

        self._image = image
        self._storage_pool = storage_pool
        self._network = network
        self._provisioning_timeout_seconds = (
            provisioning_timeout_seconds
        )
        self._agent_poll_interval_seconds = (
            agent_poll_interval_seconds
        )

    def _resolve_executable(self) -> Path:
        capability = discover_incus_vm()

        if not capability.available or capability.executable is None:
            raise IncusVmRuntimeUnavailable(
                capability.reason
                or "Incus VM runtime unavailable"
            )

        return capability.executable

    def _ensure_local_vm_image(
        self,
        executable: Path,
    ) -> None:
        completed = subprocess.run(
            [
                str(executable),
                "image",
                "info",
                self._image,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if completed.returncode != 0:
            raise IncusVmRuntimeUnavailable(
                "Required local Incus VM image is unavailable: "
                f"{self._image}. Provision it before execution."
            )

        image_type = None

        for line in completed.stdout.splitlines():
            if line.startswith("Type:"):
                image_type = line.partition(":")[2].strip()
                break

        if image_type != "virtual-machine":
            raise IncusVmRuntimeUnavailable(
                f"Incus image {self._image!r} is not a "
                "virtual-machine image"
            )

    def _instance_name(self) -> str:
        return f"dataworc-vm-{uuid4().hex[:12]}"

    def _validate_request(
        self,
        request: SandboxRequest,
    ) -> None:
        if not request.command:
            raise ValueError(
                "Sandbox command must not be empty"
            )

        if request.limits.cpu_count <= 0:
            raise ValueError(
                "CPU limit must be greater than zero"
            )

        if not float(request.limits.cpu_count).is_integer():
            raise ValueError(
                "Incus VM CPU limit must be a whole number "
                "of virtual CPUs"
            )

        if request.limits.memory_mb <= 0:
            raise ValueError(
                "Memory limit must be greater than zero"
            )

        if request.limits.timeout_seconds <= 0:
            raise ValueError(
                "Timeout must be greater than zero"
            )

        if request.limits.pids <= 0:
            raise ValueError(
                "PID limit must be greater than zero"
            )

    def _build_create_command(
        self,
        executable: Path,
        instance_name: str,
        request: SandboxRequest,
    ) -> list[str]:
        # Created stopped: with --no-profiles, `launch --device` can only
        # override profile devices, so the workspace disk must be added
        # before the first start.
        command = [
            str(executable),
            "init",
            self._image,
            instance_name,
            "--vm",
            "--ephemeral",
            "--no-profiles",
            "--storage",
            self._storage_pool,
            "--config",
            f"limits.cpu={int(request.limits.cpu_count)}",
            "--config",
            f"limits.memory={request.limits.memory_mb}MiB",
        ]

        if request.network_enabled:
            command.extend(
                [
                    "--network",
                    self._network,
                ]
            )

        return command

    @staticmethod
    def _build_workspace_device_command(
        executable: Path,
        instance_name: str,
        request: SandboxRequest,
    ) -> list[str] | None:
        if request.working_directory is None:
            return None

        workspace = request.working_directory.resolve()

        if not workspace.exists():
            raise FileNotFoundError(
                f"Sandbox workspace does not exist: {workspace}"
            )

        readonly = (
            "false"
            if request.writable_workspace
            else "true"
        )

        return [
            str(executable),
            "config",
            "device",
            "add",
            instance_name,
            "workspace",
            "disk",
            f"source={workspace}",
            "path=/workspace",
            f"readonly={readonly}",
        ]

    def _build_exec_command(
        self,
        executable: Path,
        instance_name: str,
        request: SandboxRequest,
    ) -> list[str]:
        command = [
            str(executable),
            "exec",
            instance_name,
            "--force-noninteractive",
            "--",
            "systemd-run",
            "--quiet",
            "--wait",
            "--collect",
            "--pipe",
            "--service-type=exec",
            f"--property=TasksMax={request.limits.pids}",
        ]

        if request.working_directory is not None:
            command.append(
                "--working-directory=/workspace"
            )

        for key, value in request.environment.items():
            command.append(
                f"--setenv={key}={value}"
            )

        command.append("--")
        command.extend(request.command)

        return command

    def _wait_for_agent(
        self,
        executable: Path,
        instance_name: str,
    ) -> tuple[bool, str]:
        deadline = (
            time.monotonic()
            + self._provisioning_timeout_seconds
        )

        last_error = ""

        while time.monotonic() < deadline:
            try:
                completed = subprocess.run(
                    [
                        str(executable),
                        "exec",
                        instance_name,
                        "--force-noninteractive",
                        "--",
                        "true",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                last_error = (
                    "Timed out waiting for Incus VM agent"
                )
            else:
                if completed.returncode == 0:
                    return True, ""

                last_error = (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or "Incus VM agent not ready"
                )

            time.sleep(
                self._agent_poll_interval_seconds
            )

        return False, last_error

    @staticmethod
    def _instance_exists(
        executable: Path,
        instance_name: str,
    ) -> bool:
        completed = subprocess.run(
            [
                str(executable),
                "list",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        if completed.returncode != 0:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "Incus instance verification failed"
            )

            raise IncusVmCleanupError(detail)

        try:
            payload = json.loads(
                completed.stdout
            )
        except json.JSONDecodeError as exc:
            raise IncusVmCleanupError(
                "Invalid Incus list response"
            ) from exc

        if not isinstance(payload, list):
            raise IncusVmCleanupError(
                "Unexpected Incus list response"
            )

        return any(
            isinstance(item, dict)
            and item.get("name") == instance_name
            for item in payload
        )

    def _cleanup(
        self,
        executable: Path,
        instance_name: str,
    ) -> None:
        if not self._instance_exists(
            executable,
            instance_name,
        ):
            return

        subprocess.run(
            [
                str(executable),
                "stop",
                instance_name,
                "--force",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        if not self._instance_exists(
            executable,
            instance_name,
        ):
            return

        subprocess.run(
            [
                str(executable),
                "delete",
                instance_name,
                "--force",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        if self._instance_exists(
            executable,
            instance_name,
        ):
            raise IncusVmCleanupError(
                "Incus instance survived cleanup: "
                f"{instance_name}"
            )

    def execute(
        self,
        request: SandboxRequest,
    ) -> SandboxResult:
        self._validate_request(request)

        executable = self._resolve_executable()
        self._ensure_local_vm_image(executable)

        instance_name = self._instance_name()

        provisioning_commands = [
            self._build_create_command(
                executable,
                instance_name,
                request,
            ),
            self._build_workspace_device_command(
                executable,
                instance_name,
                request,
            ),
            [
                str(executable),
                "start",
                instance_name,
            ],
        ]

        launch_command = provisioning_commands[0]

        lifecycle_started = time.monotonic()

        try:
            for provisioning_command in provisioning_commands:
                if provisioning_command is None:
                    continue

                provisioning_completed = subprocess.run(
                    provisioning_command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self._provisioning_timeout_seconds,
                )

                if provisioning_completed.returncode != 0:
                    return SandboxResult(
                        runtime_kind=self.runtime_kind,
                        isolation_class=IsolationClass.HARDWARE,
                        command=tuple(provisioning_command),
                        exit_code=(
                            provisioning_completed.returncode
                        ),
                        stdout=provisioning_completed.stdout,
                        stderr=provisioning_completed.stderr,
                        timed_out=False,
                        duration_seconds=(
                            time.monotonic()
                            - lifecycle_started
                        ),
                    )

            agent_ready, agent_error = (
                self._wait_for_agent(
                    executable,
                    instance_name,
                )
            )

            if not agent_ready:
                return SandboxResult(
                    runtime_kind=self.runtime_kind,
                    isolation_class=IsolationClass.HARDWARE,
                    command=tuple(launch_command),
                    exit_code=125,
                    stdout="",
                    stderr=(
                        "Incus VM agent did not become ready"
                        + (
                            f": {agent_error}"
                            if agent_error
                            else ""
                        )
                    ),
                    timed_out=False,
                    duration_seconds=(
                        time.monotonic()
                        - lifecycle_started
                    ),
                )

            exec_command = self._build_exec_command(
                executable,
                instance_name,
                request,
            )

            workload_started = time.monotonic()

            try:
                completed = subprocess.run(
                    exec_command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=request.limits.timeout_seconds,
                )

                return SandboxResult(
                    runtime_kind=self.runtime_kind,
                    isolation_class=IsolationClass.HARDWARE,
                    command=tuple(exec_command),
                    exit_code=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    timed_out=False,
                    duration_seconds=(
                        time.monotonic()
                        - workload_started
                    ),
                )

            except subprocess.TimeoutExpired as exc:
                stdout = (
                    exc.stdout
                    if isinstance(exc.stdout, str)
                    else ""
                )

                stderr = (
                    exc.stderr
                    if isinstance(exc.stderr, str)
                    else ""
                )

                return SandboxResult(
                    runtime_kind=self.runtime_kind,
                    isolation_class=IsolationClass.HARDWARE,
                    command=tuple(exec_command),
                    exit_code=124,
                    stdout=stdout,
                    stderr=stderr,
                    timed_out=True,
                    duration_seconds=(
                        time.monotonic()
                        - workload_started
                    ),
                )

        finally:
            self._cleanup(
                executable,
                instance_name,
            )
