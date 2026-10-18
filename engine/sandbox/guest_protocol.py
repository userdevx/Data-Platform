from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PROTOCOL_VERSION = 1

READY_TYPE = "ready"
RESULT_TYPE = "result"
EXECUTE_TYPE = "execute"

PROTOCOL_FAILURE_EXIT_CODE = 125


class GuestProtocolError(ValueError):
    """Raised when a guest protocol message is malformed or incompatible."""


@dataclass(frozen=True)
class GuestExecutionResult:
    request_id: str
    exit_code: int
    stdout: str
    stderr: str


def encode_message(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(payload),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def decode_message(raw: bytes) -> dict[str, Any]:
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GuestProtocolError(
            f"Guest message is not valid UTF-8: {exc}"
        ) from exc

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise GuestProtocolError(
            f"Guest message is not valid JSON: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise GuestProtocolError(
            "Guest protocol message must be a JSON object"
        )

    return payload


def validate_ready(payload: Mapping[str, Any]) -> None:
    if payload.get("type") != READY_TYPE:
        raise GuestProtocolError(
            "Guest did not send a ready message"
        )

    protocol = payload.get("protocol")

    if protocol != PROTOCOL_VERSION:
        raise GuestProtocolError(
            "Unsupported guest protocol version: "
            f"{protocol!r}; expected {PROTOCOL_VERSION}"
        )


def build_execute_request(
    *,
    request_id: str,
    command: Sequence[str],
    environment: Mapping[str, str],
    working_directory: str | None,
    pids: int,
) -> dict[str, Any]:
    if not isinstance(request_id, str) or not request_id:
        raise GuestProtocolError(
            "Request id must be a non-empty string"
        )

    if (
        not isinstance(command, (list, tuple))
        or not command
        or not all(
            isinstance(item, str) and "\x00" not in item
            for item in command
        )
    ):
        raise GuestProtocolError(
            "Command must contain one or more strings"
        )

    if not isinstance(environment, Mapping):
        raise GuestProtocolError(
            "Environment must be a mapping"
        )

    normalized_environment: dict[str, str] = {}

    for key, value in environment.items():
        if not isinstance(key, str) or not key:
            raise GuestProtocolError(
                "Environment keys must be non-empty strings"
            )

        if not isinstance(value, str):
            raise GuestProtocolError(
                "Environment values must be strings"
            )

        if "=" in key:
            raise GuestProtocolError(
                "Environment keys cannot contain '='"
            )

        if "\x00" in key or "\x00" in value:
            raise GuestProtocolError(
                "Environment cannot contain NUL characters"
            )

        normalized_environment[key] = value

    if working_directory is not None:
        if (
            not isinstance(working_directory, str)
            or not working_directory
        ):
            raise GuestProtocolError(
                "Working directory must be a non-empty string or None"
            )

    if not isinstance(pids, int) or isinstance(pids, bool) or pids <= 0:
        raise GuestProtocolError(
            "PID limit must be a positive integer"
        )

    return {
        "type": EXECUTE_TYPE,
        "protocol": PROTOCOL_VERSION,
        "id": request_id,
        "command": list(command),
        "environment": normalized_environment,
        "working_directory": working_directory,
        "pids": pids,
    }


def parse_execution_result(
    payload: Mapping[str, Any],
    *,
    expected_request_id: str,
) -> GuestExecutionResult:
    if payload.get("type") != RESULT_TYPE:
        raise GuestProtocolError(
            "Guest did not return an execution result"
        )

    request_id = payload.get("id")

    if request_id != expected_request_id:
        raise GuestProtocolError(
            "Guest result request id does not match "
            f"the request: expected={expected_request_id!r} "
            f"actual={request_id!r}"
        )

    exit_code = payload.get(
        "exit_code",
        PROTOCOL_FAILURE_EXIT_CODE,
    )

    if (
        not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
    ):
        raise GuestProtocolError(
            "Guest result exit_code must be an integer"
        )

    stdout = payload.get("stdout", "")
    stderr = payload.get("stderr", "")

    if not isinstance(stdout, str):
        raise GuestProtocolError(
            "Guest result stdout must be a string"
        )

    if not isinstance(stderr, str):
        raise GuestProtocolError(
            "Guest result stderr must be a string"
        )

    return GuestExecutionResult(
        request_id=expected_request_id,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )
