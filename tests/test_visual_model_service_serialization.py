from __future__ import annotations

import json
from uuid import uuid4

import pytest

from services.visual_model.errors import (
    VisualModelSerializationError,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualRuntimeHealth,
)
from services.visual_model.serialization import (
    decode_json_payload,
    encode_json_payload,
    health_from_mapping,
    health_to_mapping,
    request_from_mapping,
    request_to_mapping,
    response_from_mapping,
    response_to_mapping,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_request() -> VisualModelRequest:
    return VisualModelRequest(
        request_id=runtime_value("request"),
        question=runtime_value("question"),
        image_data=b"image-data",
        media_type="image/png",
        response_schema={
            "type": "object",
        },
        source_reference=runtime_value(
            "source"
        ),
        metadata={
            "runtime": True,
        },
    )


def build_response(
    request_id: str,
) -> VisualModelResponse:
    return VisualModelResponse(
        request_id=request_id,
        provider=runtime_value("provider"),
        model_id=runtime_value("model"),
        scene_description=runtime_value(
            "description"
        ),
        entities=(
            {
                "entity_id": runtime_value(
                    "entity"
                ),
                "label": runtime_value(
                    "label"
                ),
                "confidence": 0.9,
            },
        ),
        duration_ms=2,
        validation_passed=True,
        metadata={
            "runtime": True,
        },
    )


def test_request_round_trip() -> None:
    request = build_request()

    restored = request_from_mapping(
        request_to_mapping(request)
    )

    assert restored == request
    assert (
        restored.image_data
        == request.image_data
    )


def test_response_round_trip() -> None:
    request_id = runtime_value(
        "request"
    )

    response = build_response(
        request_id
    )

    restored = response_from_mapping(
        response_to_mapping(response)
    )

    assert restored.request_id == request_id
    assert restored.provider == response.provider
    assert restored.entities == response.entities


def test_health_round_trip() -> None:
    health = VisualRuntimeHealth(
        available=True,
        provider=runtime_value(
            "provider"
        ),
        model_id=runtime_value(
            "model"
        ),
        message="ready",
        details=("detail",),
    )

    restored = health_from_mapping(
        health_to_mapping(health)
    )

    assert restored == health


def test_json_payload_round_trip() -> None:
    value = {
        "operation": "health",
    }

    encoded = encode_json_payload(
        value,
        maximum_payload_size_bytes=1024,
    )

    restored = decode_json_payload(
        encoded,
        maximum_payload_size_bytes=1024,
    )

    assert dict(restored) == value


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(
        VisualModelSerializationError,
        match="not valid JSON",
    ):
        decode_json_payload(
            b"{invalid",
            maximum_payload_size_bytes=1024,
        )


def test_non_object_json_is_rejected() -> None:
    with pytest.raises(
        VisualModelSerializationError,
        match="must be an object",
    ):
        decode_json_payload(
            json.dumps(
                ["invalid"]
            ).encode("utf-8"),
            maximum_payload_size_bytes=1024,
        )


def test_oversized_payload_is_rejected() -> None:
    with pytest.raises(
        VisualModelSerializationError,
        match="maximum size",
    ):
        decode_json_payload(
            b"x" * 20,
            maximum_payload_size_bytes=10,
        )


def test_invalid_base64_is_rejected() -> None:
    value = request_to_mapping(
        build_request()
    )
    value["image_base64"] = "not-base64!"

    with pytest.raises(
        VisualModelSerializationError,
        match="not valid base64",
    ):
        request_from_mapping(value)


def test_unknown_request_field_is_rejected() -> None:
    value = request_to_mapping(
        build_request()
    )
    value["unexpected"] = True

    with pytest.raises(
        VisualModelSerializationError,
        match="unknown fields",
    ):
        request_from_mapping(value)


def test_missing_request_field_is_rejected() -> None:
    value = request_to_mapping(
        build_request()
    )
    value.pop("question")

    with pytest.raises(
        VisualModelSerializationError,
        match="missing required fields",
    ):
        request_from_mapping(value)


def test_nan_cannot_be_encoded() -> None:
    with pytest.raises(
        VisualModelSerializationError,
        match="could not be encoded",
    ):
        encode_json_payload(
            {
                "value": float("nan"),
            },
            maximum_payload_size_bytes=1024,
        )
