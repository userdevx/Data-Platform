from __future__ import annotations

import pytest

from engine.sandbox.guest_protocol import (
    EXECUTE_TYPE,
    PROTOCOL_VERSION,
    GuestProtocolError,
    build_execute_request,
    decode_message,
    encode_message,
    parse_execution_result,
    validate_ready,
)


def test_protocol_message_round_trip() -> None:
    payload = {
        "type": "ready",
        "protocol": PROTOCOL_VERSION,
    }

    encoded = encode_message(payload)

    assert encoded.endswith(b"\n")
    assert decode_message(encoded) == payload


def test_ready_requires_matching_protocol() -> None:
    validate_ready(
        {
            "type": "ready",
            "protocol": PROTOCOL_VERSION,
        }
    )

    with pytest.raises(
        GuestProtocolError,
        match="Unsupported guest protocol version",
    ):
        validate_ready(
            {
                "type": "ready",
                "protocol": PROTOCOL_VERSION + 1,
            }
        )


def test_build_execute_request() -> None:
    request = build_execute_request(
        request_id="request-123",
        command=["/bin/sh", "-lc", "printf ok"],
        environment={"EXAMPLE": "value"},
        working_directory=None,
        pids=64,
    )

    assert request == {
        "type": EXECUTE_TYPE,
        "protocol": PROTOCOL_VERSION,
        "id": "request-123",
        "command": [
            "/bin/sh",
            "-lc",
            "printf ok",
        ],
        "environment": {
            "EXAMPLE": "value",
        },
        "working_directory": None,
        "pids": 64,
    }


def test_build_execute_request_rejects_bad_environment() -> None:
    with pytest.raises(
        GuestProtocolError,
        match="Environment values must be strings",
    ):
        build_execute_request(
            request_id="request-123",
            command=["true"],
            environment={"BAD": 1},  # type: ignore[dict-item]
            working_directory=None,
            pids=64,
        )


def test_parse_execution_result() -> None:
    result = parse_execution_result(
        {
            "type": "result",
            "id": "request-123",
            "exit_code": 17,
            "stdout": "out",
            "stderr": "err",
        },
        expected_request_id="request-123",
    )

    assert result.request_id == "request-123"
    assert result.exit_code == 17
    assert result.stdout == "out"
    assert result.stderr == "err"


def test_result_request_id_must_match() -> None:
    with pytest.raises(
        GuestProtocolError,
        match="request id does not match",
    ):
        parse_execution_result(
            {
                "type": "result",
                "id": "wrong-id",
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
            },
            expected_request_id="request-123",
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"[]\n",
        b"{not-json}\n",
        b"\xff\n",
    ],
)
def test_invalid_messages_are_rejected(
    payload: bytes,
) -> None:
    with pytest.raises(GuestProtocolError):
        decode_message(payload)


def test_empty_argument_is_a_valid_argument() -> None:
    request = build_execute_request(
        request_id="request-123",
        command=["printf", ""],
        environment={},
        working_directory=None,
        pids=8,
    )

    assert request["command"] == ["printf", ""]


@pytest.mark.parametrize(
    "command, environment, message",
    [
        (["sh", "-c", "a\x00b"], {}, "Command must contain"),
        ([], {}, "Command must contain"),
        (["true"], {"A=B": "x"}, "cannot contain '='"),
        (["true"], {"A": "x\x00"}, "NUL"),
    ],
)
def test_build_execute_request_rejects_unsafe_input(
    command, environment, message,
) -> None:
    with pytest.raises(GuestProtocolError, match=message):
        build_execute_request(
            request_id="request-123",
            command=command,
            environment=environment,
            working_directory=None,
            pids=8,
        )


def test_qemu_rejects_bad_request_before_booting() -> None:
    from engine.sandbox.models import (
        ResourceLimits,
        SandboxRequest,
        TrustLevel,
        WorkloadType,
    )
    from engine.sandbox.runtime.qemu import QemuRuntime

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.LIMITED,
        command=("true",),
        environment={"BAD=KEY": "x"},
        requires_vm_boundary=True,
        limits=ResourceLimits(
            cpu_count=1,
            memory_mb=512,
            timeout_seconds=5,
            pids=8,
        ),
    )

    with pytest.raises(ValueError, match="cannot contain '='"):
        QemuRuntime()._validate_request(request)
