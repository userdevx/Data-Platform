"""Firecracker microVM sandbox runtime (Task 09.6).

Production form of the Task 09.5 proof. One request boots one disposable
microVM and destroys it afterwards:

    pinned artifacts -> derived guest image manifest -> hash-checked
    disposable rootfs copy -> Firecracker (--no-api, no NIC, vsock only)
    -> vsock CONNECT handshake -> guest "ready" -> one execute request
    -> result -> VM killed -> run directory removed

Trust boundaries, per Task 09.2 / 09.4:

  * Firecracker binary and kernel are checked against the repository pin
    (anchored to the official release tarball) on every execution.
  * The derived guest image is checked against its build manifest and the
    current repository guest files. The rootfs bytes that boot are hashed
    while they are copied, so what runs is exactly what the manifest names.
    The manifest itself is build provenance and self-consistency only;
    durable image trust is the Task 11 image registry.

The guest is treated as untrusted: every read from the vsock has a
deadline and a size cap.

Host-crash safety (Task 09.7): Firecracker runs in its own session, so it
would outlive a host process killed by SIGTERM/SIGKILL. It is therefore
launched through setpriv --pdeathsig SIGKILL (the kernel kills the VM when
the launching thread dies), and every run directory records its owner.
Directories whose owner is dead are swept, with any VM still using them,
before the next execution.

Not wired into the selector or manager here (separate task boundary).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from engine.sandbox.process_identity import (
    process_identity_status,
    process_start_time,
)
from engine.sandbox.guest_protocol import (
    PROTOCOL_FAILURE_EXIT_CODE,
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


PIN_SCHEMA = "dataworc.sandbox.firecracker_pin.v1"
GUEST_MANIFEST_SCHEMA = "dataworc.sandbox.firecracker_guest_image.v1"

_SANDBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = _SANDBOX_ROOT.parents[1]
DEFAULT_PIN_FILE = _SANDBOX_ROOT / "images" / "firecracker" / "pinned.json"
DEFAULT_RUN_ROOT = Path("~/.cache/dataworc/sandbox/firecracker/runs")
SETPRIV = Path("/usr/bin/setpriv")
RUN_DIR_PREFIX = "dataworc-fc-"
OWNER_FILE = "owner"

# Must stay identical to GUEST_FILES in
# scripts/sandbox-tasks/firecracker_guest_image.py; a real test enforces
# parity of the resulting inputs digest.
GUEST_FILES: tuple[tuple[str, str, int], ...] = (
    (
        "engine/sandbox/images/guest/dataworc_guest_exec.py",
        "/usr/local/lib/dataworc/dataworc_guest_exec.py",
        0o644,
    ),
    (
        "engine/sandbox/images/firecracker/guest/dataworc_firecracker_agent.py",
        "/usr/local/lib/dataworc/dataworc_firecracker_agent.py",
        0o755,
    ),
    (
        "engine/sandbox/images/firecracker/guest/dataworc-firecracker-agent.service",
        "/etc/systemd/system/dataworc-firecracker-agent.service",
        0o644,
    ),
)

VSOCK_PORT = 5000
GUEST_CID = 3
BOOT_ARGS = "console=ttyS0 reboot=k panic=1"

TIMEOUT_EXIT_CODE = 124
MIN_MEMORY_MB = 256
MAX_VCPUS = 32

_HANDSHAKE_LIMIT = 64
_READY_LIMIT = 4096
_DEFAULT_MAX_RESULT_BYTES = 16 * 1024 * 1024
_COPY_CHUNK = 4 * 1024 * 1024
_UNIX_PATH_MAX = 107
_SERIAL_TAIL_LINES = 40


class FirecrackerRuntimeUnavailable(RuntimeError):
    """Host, artifacts or guest are not in a state that can run a workload."""


class FirecrackerCleanupError(RuntimeError):
    """A VM process or run directory survived teardown."""


class _ResultTooLarge(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FirecrackerArtifacts:
    firecracker: Path
    kernel: Path
    guest_image_dir: Path
    rootfs: Path
    rootfs_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_COPY_CHUNK), b""):
            digest.update(block)

    return digest.hexdigest()


def guest_inputs_digest(
    base_rootfs_sha: str,
    repo_root: Path,
) -> tuple[str, list[dict]]:
    """Same algorithm as the Task 09.4 builder's inputs_digest()."""

    digest = hashlib.sha256(base_rootfs_sha.encode())
    files: list[dict] = []

    for repo_path, guest_path, mode in GUEST_FILES:
        source = repo_root / repo_path

        if not source.is_file():
            raise FirecrackerRuntimeUnavailable(
                f"guest source file missing: {source}"
            )

        file_sha = sha256_file(source)
        digest.update(f"{guest_path}\0{mode:o}\0{file_sha}\n".encode())
        files.append(
            {
                "repo_path": repo_path,
                "guest_path": guest_path,
                "mode": f"{mode:04o}",
                "sha256": file_sha,
            }
        )

    return digest.hexdigest(), files


def guest_image_dir(store: Path, arch: str, digest: str) -> Path:
    return store.parent / f"{arch}-dataworc-{digest[:12]}"


def request_incompatibility(request: SandboxRequest) -> str | None:
    """Return why this runtime cannot run *request*, or None if it can.

    The selector uses this to route such requests to another hardware
    runtime instead of selecting Firecracker and failing at execution.
    """

    limits = request.limits

    if request.network_enabled:
        return (
            "Firecracker network access is disabled until the Sandbox "
            "network policy layer implements approved egress"
        )

    if request.working_directory is not None or request.writable_workspace:
        return "Firecracker host workspace transfer is not implemented yet"

    cpu = float(limits.cpu_count)

    if not cpu.is_integer() or not 1 <= cpu <= MAX_VCPUS:
        return f"Firecracker CPU limit must be a whole number 1..{MAX_VCPUS}"

    if limits.memory_mb < MIN_MEMORY_MB:
        return f"Firecracker requires at least {MIN_MEMORY_MB} MiB of memory"

    return None


def _host_arch() -> str:
    machine = platform.machine()
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)


def _owner_alive(run_dir: Path) -> bool | None:
    """True/False for a recorded owner, None if no owner was recorded."""

    try:
        pid_text, start = (run_dir / OWNER_FILE).read_text().split()
        pid = int(pid_text)
    except (OSError, ValueError):
        return None

    return process_identity_status(pid, start)


def _vm_processes_using(run_dir: Path) -> list[int]:
    """Pids whose argv names this run directory's VM config."""

    config = str(run_dir / "vm.json").encode()
    found = []

    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue

        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue

        if b"--config-file" in argv and config in argv:
            found.append(int(proc.name))

    return found


class FirecrackerRuntime(SandboxRuntime):
    runtime_kind = RuntimeKind.FIRECRACKER
    isolation_class = IsolationClass.HARDWARE

    def __init__(
        self,
        *,
        pin_file: Path = DEFAULT_PIN_FILE,
        repo_root: Path = REPO_ROOT,
        run_root: Path | None = None,
        guest_image_override: Path | None = None,
        boot_timeout_seconds: float = 60,
        max_result_bytes: int = _DEFAULT_MAX_RESULT_BYTES,
    ) -> None:
        if boot_timeout_seconds <= 0:
            raise ValueError("boot_timeout_seconds must be positive")

        if max_result_bytes <= 0:
            raise ValueError("max_result_bytes must be positive")

        self._pin_file = Path(pin_file)
        self._repo_root = Path(repo_root)
        self._run_root = Path(run_root or DEFAULT_RUN_ROOT).expanduser()
        self._guest_image_override = guest_image_override
        self._boot_timeout_seconds = boot_timeout_seconds
        self._max_result_bytes = max_result_bytes

    # ------------------------------------------------------------ validation

    def _validate_request(self, request: SandboxRequest) -> dict:
        limits = request.limits

        incompatibility = request_incompatibility(request)

        if incompatibility is not None:
            raise ValueError(incompatibility)

        if limits.timeout_seconds <= 0:
            raise ValueError("Timeout must be greater than zero")

        # Raises GuestProtocolError for anything the guest would reject,
        # before any VM is booted.
        return build_execute_request(
            request_id=uuid4().hex,
            command=list(request.command),
            environment=dict(request.environment),
            working_directory=None,
            pids=limits.pids,
        )

    def _validate_host(self) -> None:
        if not os.access("/dev/kvm", os.R_OK | os.W_OK):
            raise FirecrackerRuntimeUnavailable(
                "/dev/kvm is not readable and writable"
            )

    # ------------------------------------------------------------- artifacts

    def _read_json(self, path: Path, what: str) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise FirecrackerRuntimeUnavailable(
                f"{what} unreadable: {path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise FirecrackerRuntimeUnavailable(f"{what} is not an object: {path}")

        return data

    @staticmethod
    def _require_pinned_file(path: Path, expected_sha: str, what: str) -> None:
        if not path.is_file():
            raise FirecrackerRuntimeUnavailable(f"pinned {what} missing: {path}")

        if sha256_file(path) != expected_sha:
            raise FirecrackerRuntimeUnavailable(
                f"pinned {what} sha256 differs from the pin: {path}"
            )

    @staticmethod
    def _require_root_owned(path: Path) -> None:
        info = path.stat()

        if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise FirecrackerRuntimeUnavailable(
                f"{path} must be root-owned and not group/other-writable"
            )

    def resolve_artifacts(self) -> FirecrackerArtifacts:
        pin = self._read_json(self._pin_file, "Firecracker pin")

        try:
            if pin.get("schema") != PIN_SCHEMA:
                raise FirecrackerRuntimeUnavailable(
                    f"unsupported pin schema: {pin.get('schema')!r}"
                )

            arch = pin["architecture"]

            if arch != _host_arch():
                raise FirecrackerRuntimeUnavailable(
                    f"pin is for {arch}, host is {_host_arch()}"
                )

            if not SETPRIV.is_file():
                raise FirecrackerRuntimeUnavailable(f"{SETPRIV} is required")

            self._require_root_owned(SETPRIV)

            firecracker = Path(pin["firecracker"]["path"])
            self._require_root_owned(firecracker)
            self._require_pinned_file(
                firecracker, pin["firecracker"]["sha256"], "firecracker binary"
            )

            artifacts = pin["artifacts"]
            store = Path(artifacts["store"]).expanduser()
            kernel = store / artifacts["kernel"]["file"]
            self._require_pinned_file(kernel, artifacts["kernel"]["sha256"], "kernel")

            base_rootfs = store / artifacts["rootfs"]["file"]
            base_sha = artifacts["rootfs"]["sha256"]
        except (KeyError, TypeError) as exc:
            raise FirecrackerRuntimeUnavailable(
                f"pin lacks required field: {exc}"
            ) from exc

        digest, files = guest_inputs_digest(base_sha, self._repo_root)
        image_dir = self._guest_image_override or guest_image_dir(store, arch, digest)
        manifest = self._read_json(image_dir / "manifest.json", "guest image manifest")

        try:
            if manifest.get("schema") != GUEST_MANIFEST_SCHEMA:
                raise FirecrackerRuntimeUnavailable(
                    f"unsupported guest manifest schema: {manifest.get('schema')!r}"
                )

            if manifest["base"]["rootfs_sha256"] != base_sha:
                raise FirecrackerRuntimeUnavailable(
                    "guest image was built from a different base rootfs than the pin"
                )

            if manifest["inputs_sha256"] != digest or manifest["files"] != files:
                raise FirecrackerRuntimeUnavailable(
                    "guest image is stale: repository guest files changed since "
                    "it was built (run build-firecracker-guest.py)"
                )

            rootfs = image_dir / manifest["rootfs"]["file"]
            rootfs_sha = manifest["rootfs"]["sha256"]
        except (KeyError, TypeError) as exc:
            raise FirecrackerRuntimeUnavailable(
                f"guest manifest lacks required field: {exc}"
            ) from exc

        if not (isinstance(rootfs_sha, str) and len(rootfs_sha) == 64):
            raise FirecrackerRuntimeUnavailable("guest manifest rootfs sha256 invalid")

        if rootfs.is_symlink() or not rootfs.is_file():
            raise FirecrackerRuntimeUnavailable(
                f"guest rootfs missing or not a regular file: {rootfs}"
            )

        if rootfs.stat().st_mode & 0o222:
            raise FirecrackerRuntimeUnavailable(
                f"guest rootfs is writable; expected read-only: {rootfs}"
            )

        if base_rootfs.exists() and os.path.samefile(rootfs, base_rootfs):
            raise FirecrackerRuntimeUnavailable(
                "derived guest rootfs aliases the pinned base rootfs"
            )

        return FirecrackerArtifacts(
            firecracker=firecracker,
            kernel=kernel,
            guest_image_dir=image_dir,
            rootfs=rootfs,
            rootfs_sha256=rootfs_sha,
        )

    @staticmethod
    def _copy_verified(source: Path, target: Path, expected_sha: str) -> None:
        """Copy the rootfs and hash the exact bytes written."""

        digest = hashlib.sha256()
        fd = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )

        with os.fdopen(fd, "wb") as out, source.open("rb") as src:
            for block in iter(lambda: src.read(_COPY_CHUNK), b""):
                digest.update(block)
                out.write(block)

        if digest.hexdigest() != expected_sha:
            raise FirecrackerRuntimeUnavailable(
                "guest rootfs sha256 differs from its manifest; refusing to boot"
            )

    # ---------------------------------------------------------------- vsock

    @staticmethod
    def _read_line(
        client: socket.socket,
        buffer: bytearray,
        deadline: float,
        limit: int,
    ) -> bytes:
        """One newline-terminated line, bounded in time and size."""

        while True:
            end = buffer.find(b"\n")

            if end >= 0:
                if end + 1 > limit:
                    raise _ResultTooLarge
                line = bytes(buffer[: end + 1])
                del buffer[: end + 1]
                return line

            if len(buffer) > limit:
                raise _ResultTooLarge

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise TimeoutError("deadline reached")

            client.settimeout(remaining)
            chunk = client.recv(65536)

            if not chunk:
                raise ConnectionError("peer closed the connection")

            buffer.extend(chunk)

    def _connect(
        self,
        process: subprocess.Popen,
        uds_path: Path,
        deadline: float,
    ) -> tuple[socket.socket, bytearray]:
        last_error = "vsock socket not created yet"

        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise FirecrackerRuntimeUnavailable(
                    f"firecracker exited before the guest was ready "
                    f"(exit {process.returncode})"
                )

            if not uds_path.exists():
                time.sleep(0.05)
                continue

            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            buffer = bytearray()

            try:
                client.settimeout(max(0.1, deadline - time.monotonic()))
                client.connect(str(uds_path))
                client.sendall(f"CONNECT {VSOCK_PORT}\n".encode())

                reply = self._read_line(client, buffer, deadline, _HANDSHAKE_LIMIT)
                parts = reply.split()

                if len(parts) != 2 or parts[0] != b"OK" or not parts[1].isdigit():
                    raise ConnectionError(f"invalid vsock handshake reply {reply!r}")

                validate_ready(
                    decode_message(
                        self._read_line(client, buffer, deadline, _READY_LIMIT)
                    )
                )
                return client, buffer
            except (OSError, ConnectionError, GuestProtocolError, _ResultTooLarge) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                client.close()
                time.sleep(0.2)

        raise FirecrackerRuntimeUnavailable(
            f"guest agent not ready within {self._boot_timeout_seconds}s: {last_error}"
        )

    # ------------------------------------------------------- crash recovery

    def sweep_stale_runs(self) -> list[Path]:
        """Remove run directories whose owning process is dead.

        Kills any VM process still using such a directory first. Directories
        with a live owner, or with no owner recorded yet, are left alone.
        """

        if not self._run_root.is_dir():
            return []

        removed = []

        for run_dir in sorted(self._run_root.glob(f"{RUN_DIR_PREFIX}*")):
            if run_dir.is_symlink() or not run_dir.is_dir():
                continue

            if _owner_alive(run_dir) is not False:
                continue

            for pid in _vm_processes_using(run_dir):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            deadline = time.monotonic() + 5

            while _vm_processes_using(run_dir) and time.monotonic() < deadline:
                time.sleep(0.05)

            if _vm_processes_using(run_dir):
                raise FirecrackerCleanupError(
                    f"stale VM for {run_dir} survived SIGKILL"
                )

            shutil.rmtree(run_dir, ignore_errors=True)

            if run_dir.exists():
                raise FirecrackerCleanupError(f"stale run directory not removed: {run_dir}")

            removed.append(run_dir)

        return removed

    # ------------------------------------------------------------- teardown

    @staticmethod
    def _stop_vm(process: subprocess.Popen) -> None:
        for sig, wait_seconds in ((signal.SIGTERM, 3), (signal.SIGKILL, 5)):
            if process.poll() is not None:
                return

            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass

            try:
                process.wait(timeout=wait_seconds)
                return
            except subprocess.TimeoutExpired:
                continue

    @staticmethod
    def _serial_tail(serial_log: Path) -> str:
        try:
            lines = serial_log.read_text(errors="replace").splitlines()
        except OSError:
            return ""

        return "\n".join(lines[-_SERIAL_TAIL_LINES:])

    # -------------------------------------------------------------- execute

    def _result(
        self,
        request: SandboxRequest,
        *,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        timed_out: bool = False,
        started: float,
    ) -> SandboxResult:
        return SandboxResult(
            runtime_kind=self.runtime_kind,
            isolation_class=self.isolation_class,
            command=tuple(request.command),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_seconds=time.monotonic() - started,
        )

    def execute(self, request: SandboxRequest) -> SandboxResult:
        payload = self._validate_request(request)
        self._validate_host()
        artifacts = self.resolve_artifacts()

        self._run_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.sweep_stale_runs()
        run_dir = Path(tempfile.mkdtemp(prefix=RUN_DIR_PREFIX, dir=self._run_root))
        vm_id = f"dataworc-fc-{uuid4().hex[:12]}"
        rootfs_copy = run_dir / "rootfs.ext4"
        vsock_path = run_dir / "vsock.sock"
        serial_log = run_dir / "serial.log"
        config_path = run_dir / "vm.json"

        process: subprocess.Popen | None = None
        client: socket.socket | None = None

        try:
            owner_pid = os.getpid()
            owner_start = process_start_time(owner_pid)

            if owner_start is None:
                raise FirecrackerRuntimeUnavailable(
                    "unable to determine runtime owner "
                    f"start time for pid {owner_pid}"
                )

            (run_dir / OWNER_FILE).write_text(
                f"{owner_pid} {owner_start}\n",
                encoding="utf-8",
            )

            if len(str(vsock_path)) > _UNIX_PATH_MAX:
                raise FirecrackerRuntimeUnavailable(
                    f"vsock socket path too long for AF_UNIX: {vsock_path}"
                )

            self._copy_verified(artifacts.rootfs, rootfs_copy, artifacts.rootfs_sha256)

            config = {
                "boot-source": {
                    "kernel_image_path": str(artifacts.kernel),
                    "boot_args": BOOT_ARGS,
                },
                "drives": [
                    {
                        "drive_id": "rootfs",
                        "path_on_host": str(rootfs_copy),
                        "is_root_device": True,
                        "is_read_only": False,
                    }
                ],
                "machine-config": {
                    "vcpu_count": int(request.limits.cpu_count),
                    "mem_size_mib": request.limits.memory_mb,
                },
                # Deliberately no "network-interfaces": the guest has no NIC.
                "vsock": {"guest_cid": GUEST_CID, "uds_path": str(vsock_path)},
            }
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            with serial_log.open("wb") as log:
                # setpriv sets PR_SET_PDEATHSIG then execs firecracker in
                # place (same pid, argv and process group).
                process = subprocess.Popen(
                    [
                        str(SETPRIV),
                        "--pdeathsig",
                        "SIGKILL",
                        "--",
                        str(artifacts.firecracker),
                        "--id",
                        vm_id,
                        "--no-api",
                        "--config-file",
                        str(config_path),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )

            try:
                client, buffer = self._connect(
                    process,
                    vsock_path,
                    time.monotonic() + self._boot_timeout_seconds,
                )
            except FirecrackerRuntimeUnavailable as exc:
                tail = self._serial_tail(serial_log)
                raise FirecrackerRuntimeUnavailable(
                    f"{exc}" + (f"\nserial console (last lines):\n{tail}" if tail else "")
                ) from None

            started = time.monotonic()
            deadline = started + request.limits.timeout_seconds
            client.settimeout(max(0.1, deadline - started))
            client.sendall(encode_message(payload))

            try:
                raw = self._read_line(client, buffer, deadline, self._max_result_bytes)
            except TimeoutError:
                return self._result(
                    request,
                    exit_code=TIMEOUT_EXIT_CODE,
                    stderr=(
                        "Firecracker sandbox workload timed out after "
                        f"{request.limits.timeout_seconds}s"
                    ),
                    timed_out=True,
                    started=started,
                )
            except _ResultTooLarge:
                return self._result(
                    request,
                    exit_code=PROTOCOL_FAILURE_EXIT_CODE,
                    stderr=(
                        "Firecracker guest result exceeds "
                        f"{self._max_result_bytes} bytes"
                    ),
                    started=started,
                )
            except (ConnectionError, OSError) as exc:
                return self._result(
                    request,
                    exit_code=PROTOCOL_FAILURE_EXIT_CODE,
                    stderr=f"Firecracker guest connection failed: {exc}",
                    started=started,
                )

            try:
                result = parse_execution_result(
                    decode_message(raw), expected_request_id=payload["id"]
                )
            except GuestProtocolError as exc:
                return self._result(
                    request,
                    exit_code=PROTOCOL_FAILURE_EXIT_CODE,
                    stderr=f"Invalid Firecracker guest result: {exc}",
                    started=started,
                )

            return self._result(
                request,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                started=started,
            )
        finally:
            if client is not None:
                try:
                    client.close()
                except OSError:
                    pass

            if process is not None:
                self._stop_vm(process)

            shutil.rmtree(run_dir, ignore_errors=True)

            leaks = []

            if process is not None and process.poll() is None:
                leaks.append(f"firecracker pid {process.pid} still running")

            if run_dir.exists():
                leaks.append(f"run directory not removed: {run_dir}")

            if leaks:
                raise FirecrackerCleanupError("; ".join(leaks))
