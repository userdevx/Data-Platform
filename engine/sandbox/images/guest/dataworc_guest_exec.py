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

import json
import subprocess
from typing import Any, BinaryIO, Callable


PROTOCOL_VERSION = 1
PROTOCOL_FAILURE_EXIT_CODE = 125
SYSTEMD_RUN = "/usr/bin/systemd-run"


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


def build_command(
    request: dict[str, Any],
    use_systemd: bool = True,
) -> list[str]:
    """Build workload argv.

    In guests, systemd-run places each workload in a transient unit and
    applies TasksMax to that unit.

    Host-side tests may disable systemd and execute directly.
    """

    if not use_systemd:
        return list(request["command"])

    argv = [
        SYSTEMD_RUN,
        "--quiet",
        "--wait",
        "--collect",
        "--pipe",
        "--service-type=exec",
        (
            "--property=TasksMax="
            f"{request['pids']}"
        ),
    ]

    working_directory = request.get(
        "working_directory"
    )

    if working_directory is not None:
        argv.append(
            "--working-directory="
            f"{working_directory}"
        )

    for key, value in request.get(
        "environment",
        {},
    ).items():
        argv.append(
            f"--setenv={key}={value}"
        )

    argv.append("--")
    argv.extend(request["command"])

    return argv


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

        return failure(
            request_id,
            error,
        )

    request_id = request["id"]

    try:
        completed = subprocess.run(
            build_command(
                request,
                use_systemd,
            ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            env=(
                None
                if use_systemd
                else dict(
                    request.get(
                        "environment",
                        {},
                    )
                )
            ),
            cwd=(
                None
                if use_systemd
                else request.get(
                    "working_directory"
                )
            ),
        )

    except Exception as exc:
        return failure(
            request_id,
            f"{type(exc).__name__}: {exc}",
        )

    return {
        "type": "result",
        "id": request_id,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
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
