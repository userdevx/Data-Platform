from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from engine.sandbox.guest_protocol import (
    GuestProtocolError,
    build_execute_request,
    decode_message,
    encode_message,
    parse_execution_result,
    validate_ready,
)
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
    SandboxRequest,
    SandboxResult,
)
from engine.sandbox.runtime.base import SandboxRuntime


class QemuRuntimeUnavailable(RuntimeError):
    pass


class QemuRuntime(SandboxRuntime):
    runtime_kind = RuntimeKind.QEMU_KVM

    def __init__(
        self,
        image: Path | None = None,
        ovmf_code: Path = Path(
            "/usr/share/OVMF/OVMF_CODE_4M.fd"
        ),
        ovmf_vars: Path = Path(
            "/usr/share/OVMF/OVMF_VARS_4M.fd"
        ),
        boot_timeout_seconds: int = 90,
    ) -> None:
        sandbox_root = Path(__file__).resolve().parents[1]

        self._image = (
            image
            if image is not None
            else (
                sandbox_root
                / "images"
                / "qemu"
                / "ubuntu-24.04"
                / "provisioned.qcow2"
            )
        )

        self._ovmf_code = ovmf_code
        self._ovmf_vars = ovmf_vars
        self._boot_timeout_seconds = boot_timeout_seconds

    def _resolve_qemu(self) -> Path:
        executable = shutil.which(
            "qemu-system-x86_64"
        )

        if executable is None:
            raise QemuRuntimeUnavailable(
                "qemu-system-x86_64 is not installed"
            )

        return Path(executable)

    def _resolve_qemu_img(self) -> Path:
        executable = shutil.which("qemu-img")

        if executable is None:
            raise QemuRuntimeUnavailable(
                "qemu-img is not installed"
            )

        return Path(executable)

    def _validate_host(self) -> None:
        if not os.access("/dev/kvm", os.R_OK | os.W_OK):
            raise QemuRuntimeUnavailable(
                "/dev/kvm is not readable and writable"
            )

        if not self._image.is_file():
            raise QemuRuntimeUnavailable(
                "Required local QEMU image is unavailable: "
                f"{self._image}"
            )

        if not self._ovmf_code.is_file():
            raise QemuRuntimeUnavailable(
                f"OVMF code image unavailable: {self._ovmf_code}"
            )

        if not self._ovmf_vars.is_file():
            raise QemuRuntimeUnavailable(
                f"OVMF variable image unavailable: {self._ovmf_vars}"
            )

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

        if not float(
            request.limits.cpu_count
        ).is_integer():
            raise ValueError(
                "QEMU CPU limit must be a whole number "
                "of virtual CPUs"
            )

        if request.limits.memory_mb < 256:
            raise ValueError(
                "QEMU requires at least 256 MiB of memory"
            )

        if request.limits.timeout_seconds <= 0:
            raise ValueError(
                "Timeout must be greater than zero"
            )

        if request.limits.pids <= 0:
            raise ValueError(
                "PID limit must be greater than zero"
            )

        if request.network_enabled:
            raise ValueError(
                "Direct QEMU network access is disabled until "
                "the Sandbox network policy layer explicitly "
                "implements approved egress"
            )

        if request.working_directory is not None:
            raise ValueError(
                "Direct QEMU host workspace mounting is not "
                "implemented yet"
            )

        # Reject anything the guest protocol would reject before a VM
        # is booted, not after.
        try:
            build_execute_request(
                request_id="preflight",
                command=request.command,
                environment=request.environment,
                working_directory=None,
                pids=request.limits.pids,
            )
        except GuestProtocolError as exc:
            raise ValueError(str(exc)) from exc

    def _create_overlay(
        self,
        qemu_img: Path,
        overlay: Path,
    ) -> None:
        completed = subprocess.run(
            [
                str(qemu_img),
                "create",
                "-f",
                "qcow2",
                "-F",
                "qcow2",
                "-b",
                str(self._image),
                str(overlay),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        if completed.returncode != 0:
            raise QemuRuntimeUnavailable(
                "Unable to create QEMU overlay: "
                + (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or "unknown qemu-img error"
                )
            )

    def _build_qemu_command(
        self,
        executable: Path,
        instance_name: str,
        overlay: Path,
        vars_file: Path,
        control_socket: Path,
        request: SandboxRequest,
    ) -> list[str]:
        return [
            str(executable),
            "-name",
            instance_name,
            "-enable-kvm",
            "-machine",
            "q35",
            "-cpu",
            "host",
            "-smp",
            str(int(request.limits.cpu_count)),
            "-m",
            str(request.limits.memory_mb),
            "-display",
            "none",
            "-nodefaults",
            "-no-reboot",
            "-monitor",
            "none",
            "-serial",
            "none",
            "-nic",
            "none",
            "-drive",
            (
                "if=pflash,"
                "format=raw,"
                "readonly=on,"
                f"file={self._ovmf_code}"
            ),
            "-drive",
            (
                "if=pflash,"
                "format=raw,"
                f"file={vars_file}"
            ),
            "-drive",
            (
                f"file={overlay},"
                "format=qcow2,"
                "if=virtio"
            ),
            "-device",
            "virtio-serial-pci",
            "-chardev",
            (
                "socket,"
                "id=dwcontrol,"
                f"path={control_socket},"
                "server=on,"
                "wait=off"
            ),
            "-device",
            (
                "virtserialport,"
                "chardev=dwcontrol,"
                "name=dataworc.control"
            ),
            "-object",
            "rng-random,filename=/dev/urandom,id=rng0",
            "-device",
            "virtio-rng-pci,rng=rng0",
        ]

    def _connect_control(
        self,
        process: subprocess.Popen[str],
        control_socket: Path,
    ) -> tuple[socket.socket, object]:
        deadline = (
            time.monotonic()
            + self._boot_timeout_seconds
        )

        last_error = ""

        while time.monotonic() < deadline:
            return_code = process.poll()

            if return_code is not None:
                stderr = ""

                if process.stderr is not None:
                    stderr = process.stderr.read()

                raise QemuRuntimeUnavailable(
                    "QEMU exited before the guest agent "
                    f"became ready: exit_code={return_code}"
                    + (
                        f": {stderr.strip()}"
                        if stderr.strip()
                        else ""
                    )
                )

            if not control_socket.exists():
                time.sleep(0.1)
                continue

            client = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
            )

            remaining = max(
                0.1,
                deadline - time.monotonic(),
            )

            client.settimeout(
                min(1.0, remaining)
            )

            try:
                client.connect(str(control_socket))
            except OSError as exc:
                last_error = str(exc)
                client.close()
                time.sleep(0.1)
                continue

            client.settimeout(remaining)

            stream = client.makefile(
                "rwb",
                buffering=0,
            )

            try:
                raw = stream.readline()
            except OSError as exc:
                last_error = str(exc)
                stream.close()
                client.close()
                time.sleep(0.1)
                continue

            if not raw:
                last_error = (
                    "guest agent closed control channel "
                    "before readiness"
                )
                stream.close()
                client.close()
                time.sleep(0.1)
                continue

            try:
                message = decode_message(raw)
                validate_ready(message)
            except GuestProtocolError as exc:
                last_error = str(exc)
                stream.close()
                client.close()
                time.sleep(0.1)
                continue

            return client, stream

        raise QemuRuntimeUnavailable(
            "Timed out waiting for DataWorc QEMU guest agent"
            + (
                f": {last_error}"
                if last_error
                else ""
            )
        )

    def _terminate(
        self,
        process: subprocess.Popen[str],
    ) -> None:
        if process.poll() is not None:
            return

        process.terminate()

        try:
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass

        process.kill()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def execute(
        self,
        request: SandboxRequest,
    ) -> SandboxResult:
        self._validate_request(request)
        self._validate_host()

        qemu = self._resolve_qemu()
        qemu_img = self._resolve_qemu_img()

        instance_name = (
            f"dataworc-qemu-{uuid4().hex[:12]}"
        )

        process: subprocess.Popen[str] | None = None
        client: socket.socket | None = None
        stream = None

        with tempfile.TemporaryDirectory(
            prefix="dataworc-qemu-"
        ) as temporary_directory:
            run_directory = Path(
                temporary_directory
            )

            overlay = (
                run_directory
                / "overlay.qcow2"
            )

            vars_file = (
                run_directory
                / "OVMF_VARS_4M.fd"
            )

            control_socket = (
                run_directory
                / "control.sock"
            )

            self._create_overlay(
                qemu_img,
                overlay,
            )

            shutil.copy2(
                self._ovmf_vars,
                vars_file,
            )

            launch_command = (
                self._build_qemu_command(
                    qemu,
                    instance_name,
                    overlay,
                    vars_file,
                    control_socket,
                    request,
                )
            )

            try:
                process = subprocess.Popen(
                    launch_command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                client, stream = (
                    self._connect_control(
                        process,
                        control_socket,
                    )
                )

                request_id = uuid4().hex

                payload = build_execute_request(
                    request_id=request_id,
                    command=request.command,
                    environment=request.environment,
                    working_directory=None,
                    pids=request.limits.pids,
                )

                encoded = encode_message(payload)

                client.settimeout(
                    request.limits.timeout_seconds
                )

                workload_started = (
                    time.monotonic()
                )

                stream.write(encoded)

                try:
                    raw = stream.readline()
                except (
                    socket.timeout,
                    TimeoutError,
                ):
                    return SandboxResult(
                        runtime_kind=self.runtime_kind,
                        isolation_class=(
                            IsolationClass.HARDWARE
                        ),
                        command=tuple(
                            request.command
                        ),
                        exit_code=124,
                        stdout="",
                        stderr=(
                            "QEMU sandbox workload timed out"
                        ),
                        timed_out=True,
                        duration_seconds=(
                            time.monotonic()
                            - workload_started
                        ),
                    )

                duration = (
                    time.monotonic()
                    - workload_started
                )

                if not raw:
                    stderr = ""

                    if (
                        process.stderr is not None
                        and process.poll()
                        is not None
                    ):
                        stderr = (
                            process.stderr.read()
                        )

                    return SandboxResult(
                        runtime_kind=self.runtime_kind,
                        isolation_class=(
                            IsolationClass.HARDWARE
                        ),
                        command=tuple(
                            request.command
                        ),
                        exit_code=125,
                        stdout="",
                        stderr=(
                            stderr.strip()
                            or (
                                "QEMU guest agent closed "
                                "the control channel"
                            )
                        ),
                        timed_out=False,
                        duration_seconds=duration,
                    )

                try:
                    payload = decode_message(raw)
                    result = parse_execution_result(
                        payload,
                        expected_request_id=request_id,
                    )
                except GuestProtocolError as exc:
                    return SandboxResult(
                        runtime_kind=self.runtime_kind,
                        isolation_class=(
                            IsolationClass.HARDWARE
                        ),
                        command=tuple(
                            request.command
                        ),
                        exit_code=125,
                        stdout="",
                        stderr=(
                            "Invalid QEMU guest result: "
                            f"{exc}"
                        ),
                        timed_out=False,
                        duration_seconds=duration,
                    )

                return SandboxResult(
                    runtime_kind=self.runtime_kind,
                    isolation_class=(
                        IsolationClass.HARDWARE
                    ),
                    command=tuple(
                        request.command
                    ),
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    timed_out=False,
                    duration_seconds=duration,
                )

            finally:
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass

                if client is not None:
                    try:
                        client.close()
                    except OSError:
                        pass

                if process is not None:
                    self._terminate(process)
