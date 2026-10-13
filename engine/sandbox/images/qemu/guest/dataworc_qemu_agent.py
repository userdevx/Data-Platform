#!/usr/bin/python3

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any


CONTROL_PORT = "/dev/virtio-ports/dataworc.control"


def write_message(stream: Any, payload: dict[str, Any]) -> None:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    stream.write(encoded)


def execute_request(request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id")

    command = request.get("command")
    environment = request.get("environment", {})
    working_directory = request.get("working_directory")
    pids = request.get("pids", 128)

    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) for item in command)
    ):
        return {
            "type": "result",
            "id": request_id,
            "exit_code": 125,
            "stdout": "",
            "stderr": "Invalid sandbox command",
        }

    if not isinstance(environment, dict):
        return {
            "type": "result",
            "id": request_id,
            "exit_code": 125,
            "stdout": "",
            "stderr": "Invalid sandbox environment",
        }

    if not isinstance(pids, int) or pids <= 0:
        return {
            "type": "result",
            "id": request_id,
            "exit_code": 125,
            "stdout": "",
            "stderr": "Invalid PID limit",
        }

    systemd_command = [
        "/usr/bin/systemd-run",
        "--quiet",
        "--wait",
        "--collect",
        "--pipe",
        "--service-type=exec",
        f"--property=TasksMax={pids}",
    ]

    if working_directory is not None:
        if not isinstance(working_directory, str):
            return {
                "type": "result",
                "id": request_id,
                "exit_code": 125,
                "stdout": "",
                "stderr": "Invalid working directory",
            }

        systemd_command.append(
            f"--working-directory={working_directory}"
        )

    for key, value in environment.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return {
                "type": "result",
                "id": request_id,
                "exit_code": 125,
                "stdout": "",
                "stderr": "Environment keys and values must be strings",
            }

        systemd_command.append(
            f"--setenv={key}={value}"
        )

    systemd_command.append("--")
    systemd_command.extend(command)

    try:
        completed = subprocess.run(
            systemd_command,
            capture_output=True,
            text=True,
            check=False,
        )

        return {
            "type": "result",
            "id": request_id,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    except Exception as exc:
        return {
            "type": "result",
            "id": request_id,
            "exit_code": 125,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def serve() -> None:
    while True:
        try:
            fd = os.open(
                CONTROL_PORT,
                os.O_RDWR | os.O_NOCTTY,
            )
        except OSError:
            time.sleep(0.25)
            continue

        try:
            with os.fdopen(
                fd,
                "r+b",
                buffering=0,
            ) as stream:
                write_message(
                    stream,
                    {
                        "type": "ready",
                        "protocol": 1,
                    },
                )

                while True:
                    raw = stream.readline()

                    if not raw:
                        break

                    try:
                        request = json.loads(
                            raw.decode("utf-8")
                        )
                    except Exception as exc:
                        write_message(
                            stream,
                            {
                                "type": "result",
                                "id": None,
                                "exit_code": 125,
                                "stdout": "",
                                "stderr": (
                                    "Invalid JSON request: "
                                    f"{type(exc).__name__}: {exc}"
                                ),
                            },
                        )
                        continue

                    result = execute_request(request)
                    write_message(stream, result)

        except OSError:
            time.sleep(0.25)


if __name__ == "__main__":
    serve()
