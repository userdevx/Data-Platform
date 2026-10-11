from __future__ import annotations

import subprocess
import time
from pathlib import Path

from engine.sandbox.discovery import discover_podman
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
    SandboxRequest,
    SandboxResult,
)
from engine.sandbox.runtime.base import SandboxRuntime


class PodmanRuntimeUnavailable(RuntimeError):
    pass


class PodmanRuntime(SandboxRuntime):
    runtime_kind = RuntimeKind.PODMAN

    def __init__(
        self,
        image: str = "docker.io/library/alpine:latest",
    ) -> None:
        self._image = image

    def _resolve_executable(self) -> Path:
        capability = discover_podman()

        if not capability.available or capability.executable is None:
            raise PodmanRuntimeUnavailable(
                capability.reason or "Podman runtime unavailable"
            )

        return capability.executable

    def _build_command(
        self,
        request: SandboxRequest,
    ) -> list[str]:
        executable = self._resolve_executable()

        command = [
            str(executable),
            "run",
            "--rm",
            "--pull=never",
            f"--timeout={request.limits.timeout_seconds}",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--memory={request.limits.memory_mb}m",
            f"--cpus={request.limits.cpu_count}",
            f"--pids-limit={request.limits.pids}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
        ]

        if not request.network_enabled:
            command.extend(
                [
                    "--network",
                    "none",
                ]
            )

        if request.working_directory is not None:
            workspace = request.working_directory.resolve()

            if not workspace.exists():
                raise FileNotFoundError(
                    f"Sandbox workspace does not exist: {workspace}"
                )

            mount_mode = (
                "rw"
                if request.writable_workspace
                else "ro"
            )

            command.extend(
                [
                    "--volume",
                    f"{workspace}:/workspace:{mount_mode},Z",
                    "--workdir",
                    "/workspace",
                ]
            )

        for key, value in request.environment.items():
            command.extend(
                [
                    "--env",
                    f"{key}={value}",
                ]
            )

        command.append(self._image)
        command.extend(request.command)

        return command

    def execute(
        self,
        request: SandboxRequest,
    ) -> SandboxResult:
        command = self._build_command(request)

        started = time.monotonic()

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=request.limits.timeout_seconds + 10,
            )

            duration_seconds = time.monotonic() - started

            timed_out = (
                completed.returncode == 255
                and duration_seconds
                >= request.limits.timeout_seconds
            )

            return SandboxResult(
                runtime_kind=self.runtime_kind,
                isolation_class=IsolationClass.HOST_OS,
                command=tuple(command),
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=timed_out,
                duration_seconds=duration_seconds,
            )

        except subprocess.TimeoutExpired as exc:
            duration_seconds = time.monotonic() - started

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
                isolation_class=IsolationClass.HOST_OS,
                command=tuple(command),
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_seconds=duration_seconds,
            )
