#!/usr/bin/python3
"""DataWorc guest-side execution protocol shared by guest agents.

Installed inside sandbox guests at /usr/local/lib/dataworc/.
Standard library only: the guest does not import the host engine package.

Wire contract:
  guest -> host  {"type":"ready","protocol":1}

  host -> guest  {
      "type":"execute",
      "protocol":1,
      "id":...,
      "command":[...],
      "environment":{...},
      "working_directory":...,
      "pids":N
  }

  guest -> host  {
      "type":"result",
      "id":...,
      "exit_code":N,
      "stdout":...,
      "stderr":...
  }

One JSON object per line.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import threading
from typing import Any, BinaryIO, Callable


PROTOCOL_VERSION = 1
PROTOCOL_FAILURE_EXIT_CODE = 125
SYSTEMD_RUN = "/usr/bin/systemd-run"
SYSTEMCTL = "/usr/bin/systemctl"

# Workloads start from this fixed environment plus the request's own
# variables. The agent's environment is never inherited.
BASE_ENVIRONMENT = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/root",
    "LANG": "C.UTF-8",
}

_OUTPUT_DRAIN_SECONDS = 10


def encode_message(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def failure(
    request_id: Any,
    message: str,
) -> dict[str, Any]:
    return {
        "type": "result",
        "id": (
            request_id
            if isinstance(request_id, str)
            else None
        ),
        "exit_code": PROTOCOL_FAILURE_EXIT_CODE,
        "stdout": "",
        "stderr": message,
    }


def validate_request(
    request: Any,
) -> str | None:
    """Return an error message or None if the request is valid."""

    if not isinstance(request, dict):
        return "Request must be a JSON object"

    if request.get("type") != "execute":
        return "Request type must be 'execute'"

    if request.get("protocol") != PROTOCOL_VERSION:
        return (
            f"Unsupported protocol "
            f"{request.get('protocol')!r}; "
            f"guest speaks {PROTOCOL_VERSION}"
        )

    request_id = request.get("id")

    if not isinstance(request_id, str) or not request_id:
        return "Request id must be a non-empty string"

    command = request.get("command")

    if (
        not isinstance(command, list)
        or not command
        or not all(
            isinstance(item, str)
            and "\x00" not in item
            for item in command
        )
    ):
        return "Command must contain one or more strings"

    environment = request.get(
        "environment",
        {},
    )

    if not isinstance(environment, dict):
        return "Environment must be an object"

    for key, value in environment.items():
        if (
            not isinstance(key, str)
            or not key
        ):
            return (
                "Environment keys must be "
                "non-empty strings"
            )

        if not isinstance(value, str):
            return (
                "Environment values must be strings"
            )

        if "=" in key:
            return (
                "Environment keys cannot contain '='"
            )

        if "\x00" in key or "\x00" in value:
            return (
                "Environment cannot contain "
                "NUL characters"
            )

    working_directory = request.get(
        "working_directory"
    )

    if (
        working_directory is not None
        and (
            not isinstance(
                working_directory,
                str,
            )
            or not working_directory
        )
    ):
        return (
            "Working directory must be "
            "a non-empty string or null"
        )

    pids = request.get("pids")

    if (
        not isinstance(pids, int)
        or isinstance(pids, bool)
        or pids <= 0
    ):
        return (
            "PID limit must be a positive integer"
        )

    return None


def scope_unit_name(request_id: str) -> str:
    """Deterministic, systemd-valid scope name for one request."""

    safe = re.sub(r"[^A-Za-z0-9_-]", "", request_id)[:32] or "request"
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:12]
    return f"dataworc-run-{safe}-{digest}"


def build_command(
    request: dict[str, Any],
    use_systemd: bool = True,
) -> list[str]:
    """Build workload argv.

    In guests the workload runs as ``systemd-run --scope``: systemd-run
    reaches PID 1 over its private socket (no D-Bus needed), creates a
    transient scope with TasksMax, then execs the workload in place. The
    agent therefore owns stdin/stdout/stderr and the exit status directly.

    Not a transient service: --wait/--pipe need a D-Bus system bus, which
    minimal guest images (Firecracker CI rootfs) do not have. systemd 255
    also rejects --wait and --pipe together with --scope.

    Host-side tests may disable systemd and execute directly.
    """

    if not use_systemd:
        return list(request["command"])

    return [
        SYSTEMD_RUN,
        "--quiet",
        "--scope",
        f"--unit={scope_unit_name(request['id'])}",
        f"--property=TasksMax={request['pids']}",
        "--",
        *request["command"],
    ]


def workload_environment(request: dict[str, Any]) -> dict[str, str]:
    environment = dict(BASE_ENVIRONMENT)
    environment.update(request.get("environment", {}))
    return environment


def _exit_code(returncode: int) -> int:
    return 128 - returncode if returncode < 0 else returncode


def _drain(stream: BinaryIO, sink: list[bytes]) -> None:
    try:
        for chunk in iter(lambda: stream.read(65536), b""):
            sink.append(chunk)
    except (OSError, ValueError):
        pass


def _stop_workload(
    process: subprocess.Popen,
    request: dict[str, Any],
    use_systemd: bool,
) -> None:
    """Kill anything the workload left running after its main process.

    Stray background children would otherwise keep running and hold the
    output pipes open, hanging the agent.
    """

    if use_systemd:
        # SIGKILL every process still in the request's scope cgroup,
        # including ones that left the process group (setsid). An empty
        # scope is garbage-collected by systemd; "not loaded" is fine.
        try:
            subprocess.run(
                [
                    SYSTEMCTL,
                    "kill",
                    "--signal=SIGKILL",
                    f"{scope_unit_name(request['id'])}.scope",
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def execute_request(
    request: Any,
    use_systemd: bool = True,
) -> dict[str, Any]:
    error = validate_request(request)

    if error is not None:
        request_id = (
            request.get("id")
            if isinstance(request, dict)
            else None
        )

        return failure(request_id, error)

    request_id = request["id"]

    try:
        process = subprocess.Popen(
            build_command(request, use_systemd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=workload_environment(request),
            cwd=request.get("working_directory"),
            start_new_session=True,
        )
    except Exception as exc:
        return failure(request_id, f"{type(exc).__name__}: {exc}")

    stdout: list[bytes] = []
    stderr: list[bytes] = []
    readers = [
        threading.Thread(target=_drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr), daemon=True),
    ]

    for reader in readers:
        reader.start()

    returncode = process.wait()
    _stop_workload(process, request, use_systemd)

    for reader in readers:
        reader.join(timeout=_OUTPUT_DRAIN_SECONDS)

    for pipe in (process.stdout, process.stderr):
        try:
            pipe.close()
        except OSError:
            pass

    return {
        "type": "result",
        "id": request_id,
        "exit_code": _exit_code(returncode),
        "stdout": b"".join(stdout).decode("utf-8", errors="replace"),
        "stderr": b"".join(stderr).decode("utf-8", errors="replace"),
    }


def serve_connection(
    stream: BinaryIO,
    execute: Callable[
        [Any],
        dict[str, Any],
    ] = execute_request,
) -> None:
    """Announce readiness and serve requests until EOF."""

    stream.write(
        encode_message(
            {
                "type": "ready",
                "protocol": PROTOCOL_VERSION,
            }
        )
    )

    stream.flush()

    while True:
        raw = stream.readline()

        if not raw:
            return

        try:
            request = json.loads(
                raw.decode("utf-8")
            )

        except Exception as exc:
            result = failure(
                None,
                (
                    "Invalid JSON request: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        else:
            result = execute(request)

        stream.write(
            encode_message(result)
        )

        stream.flush()
