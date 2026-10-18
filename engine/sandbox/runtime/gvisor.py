from __future__ import annotations

import subprocess
import time
from pathlib import Path
from uuid import uuid4

from engine.sandbox.discovery import discover_gvisor
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
    SandboxRequest,
    SandboxResult,
)
from engine.sandbox.runtime.base import SandboxRuntime


class GVisorRuntimeUnavailable(RuntimeError):
    pass


class GVisorCleanupError(RuntimeError):
    pass


class GVisorRuntime(SandboxRuntime):
    runtime_kind = RuntimeKind.GVISOR

    def __init__(
        self,
        image: str = "alpine:latest",
        docker_executable: str = "/usr/bin/docker",
    ) -> None:
        self._image = image
        self._docker_executable = Path(docker_executable)

    def _resolve_runsc(self) -> Path:
        capability = discover_gvisor()

        if not capability.available or capability.executable is None:
            raise GVisorRuntimeUnavailable(
                capability.reason
                or "gVisor runtime unavailable"
            )

        return capability.executable

    def _ensure_docker(self) -> Path:
        if not self._docker_executable.exists():
            raise GVisorRuntimeUnavailable(
                f"Docker executable not found: "
                f"{self._docker_executable}"
            )

        return self._docker_executable

    def _ensure_local_image(
        self,
        docker: Path,
    ) -> None:
        completed = subprocess.run(
            [
                str(docker),
                "image",
                "inspect",
                self._image,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if completed.returncode != 0:
            raise GVisorRuntimeUnavailable(
                "Required local Docker image is unavailable: "
                f"{self._image}. Provision it before execution."
            )

    def _container_name(self) -> str:
        return f"dataworc-gvisor-{uuid4().hex[:12]}"

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

    def _build_command(
        self,
        request: SandboxRequest,
        container_name: str | None = None,
    ) -> list[str]:
        self._resolve_runsc()
        docker = self._ensure_docker()

        command = [
            str(docker),
            "run",
            "--rm",
            "--runtime=runsc",
            "--pull=never",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--memory={request.limits.memory_mb}m",
            f"--cpus={request.limits.cpu_count}",
            f"--pids-limit={request.limits.pids}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
        ]

        if container_name is not None:
            command.extend(
                [
                    "--name",
                    container_name,
                ]
            )

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
                    f"{workspace}:/workspace:{mount_mode}",
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

    @staticmethod
    def _container_exists(
        docker: Path,
        container_name: str,
    ) -> bool:
        completed = subprocess.run(
            [
                str(docker),
                "ps",
                "-a",
                "--filter",
                f"name=^/{container_name}$",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

        if completed.returncode != 0:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "Docker container verification failed"
            )

            raise GVisorCleanupError(detail)

        names = {
            line.strip()
            for line in completed.stdout.splitlines()
            if line.strip()
        }

        return container_name in names

    def _cleanup(
        self,
        docker: Path,
        container_name: str,
    ) -> None:
        subprocess.run(
            [
                str(docker),
                "rm",
                "-f",
                container_name,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        if self._container_exists(
            docker,
            container_name,
        ):
            raise GVisorCleanupError(
                "gVisor container survived cleanup: "
                f"{container_name}"
            )

    def execute(
        self,
        request: SandboxRequest,
    ) -> SandboxResult:
        self._validate_request(request)

        docker = self._ensure_docker()
        self._resolve_runsc()
        self._ensure_local_image(docker)

        container_name = self._container_name()

        command = self._build_command(
            request,
            container_name=container_name,
        )

        started = time.monotonic()

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=request.limits.timeout_seconds,
            )

            return SandboxResult(
                runtime_kind=self.runtime_kind,
                isolation_class=IsolationClass.KERNEL_EMULATION,
                command=tuple(command),
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_seconds=(
                    time.monotonic() - started
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
                isolation_class=IsolationClass.KERNEL_EMULATION,
                command=tuple(command),
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_seconds=(
                    time.monotonic() - started
                ),
            )

        finally:
            self._cleanup(
                docker,
                container_name,
            )
