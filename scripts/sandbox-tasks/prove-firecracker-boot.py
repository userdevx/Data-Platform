#!/usr/bin/env python3
"""Task 09.5: manual Firecracker boot proof before FirecrackerRuntime.

Boots the verified Task 09.4 guest image once under real KVM and proves:

  - Task 09.2 pins are still valid
  - Task 09.4 derived guest image is still valid
  - pinned kernel is used
  - verified guest image is copied to a disposable writable rootfs
  - Firecracker starts under KVM
  - VM configuration has no network interface
  - Firecracker vsock becomes reachable
  - Firecracker CONNECT handshake is valid
  - guest protocol "ready" message is valid
  - request/response IDs match
  - stdout is preserved
  - stderr is preserved
  - non-zero exit codes are preserved
  - environment propagation works
  - working-directory propagation works
  - workload HOME=/root is usable; agent environment is not inherited
  - workload runs in its own systemd scope with TasksMax enforced
  - background workload processes are killed when the request ends
  - guest sees only the loopback network interface
  - guest sees the configured vCPU count
  - guest identifies the virtualization boundary as KVM
  - VM process terminates
  - vsock socket is removed
  - disposable rootfs is removed
  - run directory is removed
  - verified Task 09.4 guest image remains unchanged

This is intentionally a one-off real-machine proof. It is not the
production FirecrackerRuntime implementation.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

from firecracker_guest_image import guest_image_dir, inputs_digest  # noqa: E402
from firecracker_pins import PIN_FILE, PinError, sha256_file  # noqa: E402

from engine.sandbox.guest_protocol import (  # noqa: E402
    GuestProtocolError,
    build_execute_request,
    decode_message,
    encode_message,
    parse_execution_result,
    validate_ready,
)


VSOCK_PORT = 5000
GUEST_CID = 3

BOOT_TIMEOUT_SECONDS = 60
EXEC_TIMEOUT_SECONDS = 30

MARKER = "DATAWORC_FIRECRACKER_OK"
STDERR_MARKER = "DATAWORC_FIRECRACKER_STDERR_OK"
ENV_MARKER = "DATAWORC_FIRECRACKER_ENV_OK"

EXPECTED_VCPUS = 1
EXPECTED_MEMORY_MIB = 512


def run_check(argv: list[str]) -> None:
    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout_lines = completed.stdout.strip().splitlines()
    last = stdout_lines[-1] if stdout_lines else ""

    if (
        completed.returncode != 0
        or not last.startswith("PASS: TASK")
    ):
        raise PinError(
            f"{' '.join(argv)} failed:\n"
            f"{completed.stdout}"
            f"{completed.stderr}"
        )

    print(
        "PASS: "
        f"{last.removeprefix('PASS: ')} "
        "still valid"
    )


def close_quietly(closable: object | None) -> None:
    if closable is None:
        return

    close = getattr(closable, "close", None)

    if close is None:
        return

    try:
        close()
    except OSError:
        pass


def validate_vsock_handshake(reply: bytes) -> None:
    parts = reply.strip().split()

    if (
        len(parts) != 2
        or parts[0] != b"OK"
        or not parts[1].isdigit()
    ):
        raise ConnectionError(
            "invalid Firecracker vsock "
            f"handshake reply {reply!r}"
        )


def vsock_connect(
    uds_path: Path,
    deadline: float,
    process: subprocess.Popen,
) -> tuple[socket.socket, BinaryIO]:
    last_error = "vsock socket not created yet"

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise PinError(
                "firecracker exited early "
                f"(code {process.returncode})"
            )

        if not uds_path.exists():
            time.sleep(0.1)
            continue

        client: socket.socket | None = None
        stream: BinaryIO | None = None

        try:
            client = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
            )

            remaining = deadline - time.monotonic()

            client.settimeout(
                max(
                    0.5,
                    min(5.0, remaining),
                )
            )

            client.connect(str(uds_path))

            client.sendall(
                f"CONNECT {VSOCK_PORT}\n".encode()
            )

            stream = client.makefile(
                "rwb",
                buffering=0,
            )

            reply = stream.readline()

            if not reply:
                raise ConnectionError(
                    "Firecracker closed during "
                    "vsock CONNECT handshake"
                )

            validate_vsock_handshake(reply)

            ready = stream.readline()

            if not ready:
                raise ConnectionError(
                    "guest closed connection "
                    "before protocol ready"
                )

            validate_ready(
                decode_message(ready)
            )

            return client, stream

        except (
            OSError,
            ConnectionError,
            GuestProtocolError,
            ValueError,
        ) as exc:
            last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            close_quietly(stream)
            close_quietly(client)

            time.sleep(0.2)

    raise PinError(
        "guest agent not ready within "
        f"{BOOT_TIMEOUT_SECONDS}s: "
        f"{last_error}"
    )


def send_request(
    client: socket.socket,
    stream: BinaryIO,
    *,
    command: list[str],
    environment: dict[str, str] | None = None,
    working_directory: str | None = None,
    pids: int = 64,
):
    request_id = uuid4().hex

    request = build_execute_request(
        request_id=request_id,
        command=command,
        environment=(
            environment
            if environment is not None
            else {}
        ),
        working_directory=working_directory,
        pids=pids,
    )

    client.settimeout(EXEC_TIMEOUT_SECONDS)

    stream.write(
        encode_message(request)
    )

    raw = stream.readline()

    if not raw:
        raise PinError(
            "guest closed connection "
            f"while waiting for request {request_id}"
        )

    result = parse_execution_result(
        decode_message(raw),
        expected_request_id=request_id,
    )

    print(
        "PASS: response id matches "
        f"request id {request_id}"
    )

    return result


def stop_vm(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    for sig, wait_seconds in (
        (signal.SIGTERM, 3),
        (signal.SIGKILL, 5),
    ):
        try:
            os.killpg(
                process.pid,
                sig,
            )
        except ProcessLookupError:
            return

        try:
            process.wait(
                timeout=wait_seconds
            )
            return
        except subprocess.TimeoutExpired:
            continue


def save_failure_log(
    serial_log: Path,
    saved_log: Path,
) -> None:
    if not serial_log.exists():
        return

    saved_log.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copyfile(
        serial_log,
        saved_log,
    )

    print(
        "serial console saved to "
        f"{saved_log}; last lines:"
    )

    lines = serial_log.read_text(
        errors="replace"
    ).splitlines()

    print(
        "\n".join(
            lines[-40:]
        )
    )


def main() -> None:
    if Path.cwd().resolve() != REPO_ROOT:
        raise PinError(
            "run Task 09.5 from repository root: "
            f"{REPO_ROOT}"
        )

    if not os.access(
        "/dev/kvm",
        os.R_OK | os.W_OK,
    ):
        raise PinError(
            "/dev/kvm is not readable and "
            "writable by this user"
        )

    print("PASS: /dev/kvm accessible")

    run_check(
        [
            sys.executable,
            str(
                HERE
                / "verify-firecracker-pins.py"
            ),
        ]
    )

    run_check(
        [
            sys.executable,
            str(
                HERE
                / "build-firecracker-guest.py"
            ),
            "--verify",
        ]
    )

    pin = json.loads(
        PIN_FILE.read_text(
            encoding="utf-8"
        )
    )

    artifacts = pin["artifacts"]

    store = Path(
        artifacts["store"]
    ).expanduser()

    kernel = (
        store
        / artifacts["kernel"]["file"]
    )

    if not kernel.is_file():
        raise PinError(
            "pinned Firecracker kernel "
            f"missing: {kernel}"
        )

    if (
        sha256_file(kernel)
        != artifacts["kernel"]["sha256"]
    ):
        raise PinError(
            "pinned Firecracker kernel "
            "sha256 changed before boot"
        )

    digest, _ = inputs_digest(
        artifacts["rootfs"]["sha256"],
        REPO_ROOT,
    )

    guest_dir = guest_image_dir(
        store,
        pin["architecture"],
        digest,
    )

    guest_rootfs = (
        guest_dir
        / "rootfs.ext4"
    )

    guest_manifest = (
        guest_dir
        / "manifest.json"
    )

    if not guest_rootfs.is_file():
        raise PinError(
            "verified Task 09.4 guest rootfs "
            f"missing: {guest_rootfs}"
        )

    if not guest_manifest.is_file():
        raise PinError(
            "verified Task 09.4 guest manifest "
            f"missing: {guest_manifest}"
        )

    guest_sha_before = sha256_file(
        guest_rootfs
    )

    print(
        "PASS: verified guest rootfs "
        f"sha256 {guest_sha_before}"
    )

    vm_id = (
        "dataworc-fc-"
        f"{uuid4().hex[:12]}"
    )

    run_dir = Path(
        tempfile.mkdtemp(
            prefix="dataworc-fc-"
        )
    )

    rootfs_copy = (
        run_dir
        / "rootfs.ext4"
    )

    vsock_path = (
        run_dir
        / "vsock.sock"
    )

    serial_log = (
        run_dir
        / "serial.log"
    )

    config_path = (
        run_dir
        / "vm.json"
    )

    saved_log = (
        Path.home()
        / "logs"
        / f"{vm_id}-serial.log"
    )

    process: subprocess.Popen | None = None
    client: socket.socket | None = None
    stream: BinaryIO | None = None
    failure: BaseException | None = None

    try:
        shutil.copyfile(
            guest_rootfs,
            rootfs_copy,
        )

        if os.path.samefile(
            guest_rootfs,
            rootfs_copy,
        ):
            raise PinError(
                "disposable rootfs aliases "
                "verified guest image"
            )

        os.chmod(
            rootfs_copy,
            0o600,
        )

        print(
            "PASS: disposable rootfs copy "
            f"{rootfs_copy}"
        )

        config = {
            "boot-source": {
                "kernel_image_path": (
                    str(kernel)
                ),
                "boot_args": (
                    "console=ttyS0 "
                    "reboot=k "
                    "panic=1"
                ),
            },
            "drives": [
                {
                    "drive_id": "rootfs",
                    "path_on_host": (
                        str(rootfs_copy)
                    ),
                    "is_root_device": True,
                    "is_read_only": False,
                }
            ],
            "machine-config": {
                "vcpu_count": (
                    EXPECTED_VCPUS
                ),
                "mem_size_mib": (
                    EXPECTED_MEMORY_MIB
                ),
            },
            "vsock": {
                "guest_cid": GUEST_CID,
                "uds_path": (
                    str(vsock_path)
                ),
            },
        }

        if "network-interfaces" in config:
            raise PinError(
                "Task 09.5 config unexpectedly "
                "contains network-interfaces"
            )

        config_path.write_text(
            json.dumps(
                config,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            "PASS: VM config has no "
            "network interface; vsock only"
        )

        firecracker = Path(
            pin["firecracker"]["path"]
        )

        if not firecracker.is_file():
            raise PinError(
                "pinned Firecracker executable "
                f"missing: {firecracker}"
            )

        started = time.monotonic()

        log_handle = serial_log.open("wb")

        try:
            process = subprocess.Popen(
                [
                    str(firecracker),
                    "--id",
                    vm_id,
                    "--no-api",
                    "--config-file",
                    str(config_path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()

        print(
            "PASS: firecracker started "
            f"pid={process.pid} "
            f"id={vm_id}"
        )

        client, stream = vsock_connect(
            vsock_path,
            started + BOOT_TIMEOUT_SECONDS,
            process,
        )

        boot_seconds = (
            time.monotonic()
            - started
        )

        print(
            "PASS: guest agent ready "
            "over vsock in "
            f"{boot_seconds:.2f}s"
        )

        system_result = send_request(
            client,
            stream,
            command=[
                "/bin/sh",
                "-c",
                (
                    f"echo {MARKER}; "
                    "ls /sys/class/net "
                    "| sort "
                    "| tr '\\n' ' '; "
                    "echo; "
                    "nproc; "
                    "awk "
                    "'/MemTotal/ "
                    "{print $2}' "
                    "/proc/meminfo; "
                    "systemd-detect-virt "
                    "|| true"
                ),
            ],
            pids=64,
        )

        system_lines = [
            line.strip()
            for line
            in system_result.stdout.splitlines()
        ]

        if (
            system_result.exit_code != 0
            or MARKER not in system_lines
        ):
            raise PinError(
                "guest system proof failed: "
                f"exit={system_result.exit_code}\n"
                f"stdout:\n"
                f"{system_result.stdout}\n"
                f"stderr:\n"
                f"{system_result.stderr}"
            )

        print(
            "PASS: guest executed command, "
            f"stdout captured ({MARKER})"
        )

        start = system_lines.index(
            MARKER
        )

        if len(system_lines) < start + 5:
            raise PinError(
                "guest system proof produced "
                "incomplete stdout:\n"
                f"{system_result.stdout}"
            )

        interfaces = (
            system_lines[start + 1].split()
        )

        vcpus = system_lines[start + 2]
        mem_kib = system_lines[start + 3]
        virt = system_lines[start + 4]

        if interfaces != ["lo"]:
            raise PinError(
                "guest has network interfaces "
                "besides loopback: "
                f"{interfaces}"
            )

        print(
            "PASS: guest network "
            "interfaces = lo only"
        )

        if vcpus != str(
            EXPECTED_VCPUS
        ):
            raise PinError(
                "guest sees "
                f"{vcpus} vCPUs; "
                "configured "
                f"{EXPECTED_VCPUS}"
            )

        if virt != "kvm":
            raise PinError(
                "guest virtualization is "
                f"{virt!r}, expected 'kvm'"
            )

        print(
            "PASS: KVM guest, "
            f"{vcpus} vCPU, "
            f"MemTotal {mem_kib} KiB "
            f"({EXPECTED_MEMORY_MIB} MiB configured)"
        )

        error_result = send_request(
            client,
            stream,
            command=[
                "/bin/sh",
                "-c",
                (
                    f"echo {STDERR_MARKER} >&2; "
                    "exit 7"
                ),
            ],
            pids=16,
        )

        if error_result.exit_code != 7:
            raise PinError(
                "guest exit code was "
                f"{error_result.exit_code}; "
                "expected 7"
            )

        if (
            STDERR_MARKER
            not in error_result.stderr
        ):
            raise PinError(
                "guest stderr marker missing:\n"
                f"{error_result.stderr}"
            )

        print(
            "PASS: guest stderr captured "
            "and non-zero exit code preserved"
        )

        env_result = send_request(
            client,
            stream,
            command=[
                "/bin/sh",
                "-c",
                (
                    'printf "%s|%s\\n" '
                    '"$DATAWORC_TEST_MARKER" '
                    '"$(pwd)"'
                ),
            ],
            environment={
                "DATAWORC_TEST_MARKER": (
                    ENV_MARKER
                ),
            },
            working_directory="/tmp",
            pids=16,
        )

        expected_env_line = (
            f"{ENV_MARKER}|/tmp"
        )

        if env_result.exit_code != 0:
            raise PinError(
                "environment/cwd proof failed: "
                f"exit={env_result.exit_code}\n"
                f"{env_result.stderr}"
            )

        if (
            env_result.stdout.strip()
            != expected_env_line
        ):
            raise PinError(
                "environment/cwd proof returned "
                f"{env_result.stdout!r}; "
                f"expected {expected_env_line!r}"
            )

        print(
            "PASS: guest environment and "
            "working directory propagated"
        )

        # ---- workload isolation: fixed environment, HOME usable ----

        isolation_result = send_request(
            client,
            stream,
            command=[
                "/bin/sh",
                "-c",
                (
                    'printf "HOME=%s\\n" "$HOME"; '
                    'test -d "$HOME" && echo HOME_DIR_OK; '
                    "env | cut -d= -f1 | sort | tr '\\n' ' '; "
                    "echo"
                ),
            ],
            pids=16,
        )

        isolation_lines = isolation_result.stdout.splitlines()

        if (
            isolation_result.exit_code != 0
            or "HOME=/root" not in isolation_lines
            or "HOME_DIR_OK" not in isolation_lines
        ):
            raise PinError(
                "workload HOME proof failed: "
                f"exit={isolation_result.exit_code}\n"
                f"{isolation_result.stdout}\n"
                f"{isolation_result.stderr}"
            )

        workload_keys = set(isolation_lines[-1].split())
        # INVOCATION_ID is expected here: systemd creates a new
        # invocation identifier for the transient workload scope itself.
        # It is therefore not evidence that the guest agent environment
        # leaked into the workload.
        forbidden_agent_keys = {
            "JOURNAL_STREAM",
            "SYSTEMD_EXEC_PID",
        } & workload_keys

        if forbidden_agent_keys:
            raise PinError(
                "workload inherited forbidden agent environment: "
                f"{sorted(forbidden_agent_keys)}"
            )

        print(
            "PASS: workload HOME=/root usable; "
            "agent environment not inherited "
            f"(keys: {' '.join(sorted(workload_keys))})"
        )

        if "INVOCATION_ID" in workload_keys:
            print(
                "PASS: workload has its own systemd "
                "INVOCATION_ID scope metadata"
            )

        # ---- PID limit: TasksMax enforced on the workload scope ----

        pids_limit = 8

        pids_result = send_request(
            client,
            stream,
            command=[
                "/bin/sh",
                "-c",
                (
                    # Resolve the cgroup before the limit is exhausted;
                    # after the fork storm only fork-free builtins run.
                    "cg=/sys/fs/cgroup$(grep '^0::' /proc/self/cgroup | cut -d: -f3-); "
                    'echo "CGROUP=$cg"; '
                    'read m < "$cg/pids.max"; echo "PIDS_MAX=$m"; '
                    "( i=0; while [ $i -lt 20 ]; do "
                    "sleep 30 & i=$((i+1)); done ) 2>/dev/null; "
                    'read c < "$cg/pids.current"; echo "PIDS_CURRENT=$c"; '
                    'while read k v; do [ "$k" = max ] && echo "PIDS_EVENTS_MAX=$v"; '
                    'done < "$cg/pids.events"; '
                    "exit 0"
                ),
            ],
            pids=pids_limit,
        )

        values = dict(
            line.split("=", 1)
            for line in pids_result.stdout.splitlines()
            if "=" in line
        )

        cgroup_path = values.get("CGROUP", "")

        if "/dataworc-run-" not in cgroup_path or not cgroup_path.endswith(".scope"):
            raise PinError(
                "workload is not in its own dataworc scope: "
                f"{pids_result.stdout}\n{pids_result.stderr}"
            )

        if values.get("PIDS_MAX") != str(pids_limit):
            raise PinError(
                f"pids.max is {values.get('PIDS_MAX')!r}; "
                f"expected {pids_limit}\n{pids_result.stdout}"
            )

        current = int(values.get("PIDS_CURRENT", "-1"))
        refused = int(values.get("PIDS_EVENTS_MAX", "0"))

        if not 0 < current <= pids_limit:
            raise PinError(
                f"pids.current {current} outside 1..{pids_limit}"
            )

        if refused <= 0:
            raise PinError(
                "no fork was refused by the PID limit "
                f"(pids.events max={refused})"
            )

        print(
            f"PASS: workload scope {cgroup_path.rsplit('/', 1)[-1]}"
        )
        print(
            f"PASS: TasksMax enforced: pids.max={pids_limit}, "
            f"pids.current={current} after 20 forks, "
            f"{refused} forks refused"
        )

        # ---- cleanup: background children killed after the request ----

        leftover_result = send_request(
            client,
            stream,
            command=[
                "/bin/sh",
                "-c",
                (
                    "n=0; "
                    "for f in /proc/[0-9]*/cmdline; do "
                    "c=$(tr '\\0' ' ' < $f 2>/dev/null); "
                    'case "$c" in "sleep 30 ") n=$((n+1));; esac; '
                    "done; "
                    'echo "LEFTOVER_SLEEPS=$n"'
                ),
            ],
            pids=16,
        )

        if leftover_result.stdout.strip() != "LEFTOVER_SLEEPS=0":
            raise PinError(
                "workload children survived their request: "
                f"{leftover_result.stdout!r}"
            )

        print(
            "PASS: background workload processes "
            "killed when the request ended"
        )

    except BaseException as exc:
        failure = exc

        save_failure_log(
            serial_log,
            saved_log,
        )

    finally:
        close_quietly(stream)
        close_quietly(client)

        if process is not None:
            stop_vm(process)

        shutil.rmtree(
            run_dir,
            ignore_errors=True,
        )

    cleanup_errors: list[str] = []

    if process is not None:
        process.poll()

        if process.returncode is None:
            cleanup_errors.append(
                "firecracker process still running: "
                f"pid={process.pid}"
            )
        else:
            print(
                "PASS: VM killed "
                "(firecracker exit "
                f"{process.returncode})"
            )

    residual = subprocess.run(
        [
            "pgrep",
            "-f",
            vm_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if residual.returncode == 0:
        cleanup_errors.append(
            "process for VM id still running: "
            f"{vm_id}\n"
            f"{residual.stdout}"
        )
    else:
        print(
            "PASS: no residual process "
            f"for {vm_id}"
        )

    for label, path in (
        ("vsock socket", vsock_path),
        ("rootfs copy", rootfs_copy),
        ("run directory", run_dir),
    ):
        if path.exists():
            cleanup_errors.append(
                f"{label} not removed: {path}"
            )
        else:
            print(
                f"PASS: {label} removed"
            )

    guest_sha_after = sha256_file(
        guest_rootfs
    )

    if (
        guest_sha_after
        != guest_sha_before
    ):
        cleanup_errors.append(
            "verified Task 09.4 guest image "
            "changed during boot proof: "
            f"before={guest_sha_before} "
            f"after={guest_sha_after}"
        )
    else:
        print(
            "PASS: verified guest image unchanged"
        )

    if cleanup_errors:
        raise PinError(
            "Task 09.5 cleanup/integrity "
            "failure:\n"
            + "\n".join(
                cleanup_errors
            )
        )

    if failure is not None:
        raise failure

    print("PASS: TASK 09.5")


if __name__ == "__main__":
    main()
