from __future__ import annotations

from uuid import uuid4

import pytest

from services.visual_model.errors import (
    VisualModelRequestValidationError,
    VisualModelResponseValidationError,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualModelRuntime,
    VisualRuntimeHealth,
)
from services.visual_model.validation import (
    validate_visual_model_request,
    validate_visual_model_response,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_request(
    **overrides,
) -> VisualModelRequest:
    values = {
        "request_id": runtime_value(
            "request"
        ),
        "question": runtime_value(
            "question"
        ),
        "image_data": b"runtime-image-data",
        "media_type": "image/png",
        "response_schema": {
            "type": "object",
        },
        "source_reference": runtime_value(
            "source"
        ),
        "metadata": {
            "runtime": True,
        },
    }
    values.update(overrides)
    return VisualModelRequest(**values)


def build_response(
    request_id: str,
    **overrides,
) -> VisualModelResponse:
    values = {
        "request_id": request_id,
        "provider": runtime_value(
            "provider"
        ),
        "model_id": runtime_value(
            "model"
        ),
        "scene_description": runtime_value(
            "description"
        ),
        "entities": (
            {
                "entity_id": runtime_value(
                    "entity"
                ),
                "label": runtime_value(
                    "label"
                ),
                "confidence": 0.91,
            },
        ),
        "relations": (),
        "visible_text": (),
        "uncertainty": (),
        "duration_ms": 10,
        "validation_passed": True,
        "warnings": (),
        "metadata": {
            "runtime": True,
        },
    }
    values.update(overrides)
    return VisualModelResponse(**values)


def test_request_normalizes_text_and_media_type() -> None:
    request = build_request(
        question="  describe   visible evidence  ",
        media_type=" IMAGE/PNG ",
    )

    assert (
        request.question
        == "describe visible evidence"
    )
    assert request.media_type == "image/png"


def test_request_record_excludes_image_data() -> None:
    request = build_request()

    record = request.to_record()

    assert "image_data" not in record
    assert (
        record["image_size_bytes"]
        == len(request.image_data)
    )


def test_request_data_is_immutable() -> None:
    request = build_request()

    with pytest.raises(TypeError):
        request.metadata["changed"] = True


def test_valid_request_passes_validation() -> None:
    request = build_request()

    validate_visual_model_request(
        request,
        maximum_image_size_bytes=1024,
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"request_id": ""},
            "request_id is required",
        ),
        (
            {"question": ""},
            "question is required",
        ),
        (
            {"image_data": b""},
            "image_data is required",
        ),
        (
            {"media_type": "application/octet-stream"},
            "media_type is not allowed",
        ),
        (
            {"response_schema": {}},
            "response_schema is required",
        ),
    ],
)
def test_invalid_requests_are_rejected(
    overrides,
    message: str,
) -> None:
    request = build_request(
        **overrides
    )

    with pytest.raises(
        VisualModelRequestValidationError,
        match=message,
    ):
        validate_visual_model_request(
            request,
            maximum_image_size_bytes=1024,
        )


def test_oversized_image_is_rejected() -> None:
    request = build_request(
        image_data=b"x" * 20,
    )

    with pytest.raises(
        VisualModelRequestValidationError,
        match="exceeds",
    ):
        validate_visual_model_request(
            request,
            maximum_image_size_bytes=10,
        )


def test_response_normalizes_collections() -> None:
    request_id = runtime_value(
        "request"
    )

    response = build_response(
        request_id,
        visible_text=(
            "  visible text  ",
            "",
        ),
        warnings=(
            "  warning  ",
            "",
        ),
    )

    assert response.visible_text == (
        "visible text",
    )
    assert response.warnings == (
        "warning",
    )


def test_response_record_is_serializable_shape() -> None:
    request_id = runtime_value(
        "request"
    )

    response = build_response(
        request_id
    )

    record = response.to_record()

    assert record["request_id"] == request_id
    assert isinstance(
        record["entities"],
        list,
    )
    assert isinstance(
        record["metadata"],
        dict,
    )


def test_valid_response_passes_validation() -> None:
    request_id = runtime_value(
        "request"
    )

    validate_visual_model_response(
        build_response(request_id),
        expected_request_id=request_id,
    )


def test_response_request_id_must_match() -> None:
    response = build_response(
        runtime_value("request")
    )

    with pytest.raises(
        VisualModelResponseValidationError,
        match="does not match",
    ):
        validate_visual_model_response(
            response,
            expected_request_id=runtime_value(
                "different-request"
            ),
        )


def test_negative_duration_is_rejected() -> None:
    request_id = runtime_value(
        "request"
    )

    response = build_response(
        request_id,
        duration_ms=-1,
    )

    with pytest.raises(
        VisualModelResponseValidationError,
        match="cannot be negative",
    ):
        validate_visual_model_response(
            response,
            expected_request_id=request_id,
        )


class CompatibleRuntime:
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        return VisualRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        return build_response(
            request.request_id
        )


def test_runtime_protocol_is_provider_independent() -> None:
    runtime = CompatibleRuntime()

    assert isinstance(
        runtime,
        VisualModelRuntime,
    )

    request = build_request()
    response = runtime.analyze(request)

    assert (
        response.request_id
        == request.request_id
    )


def test_contracts_contain_no_hidden_reasoning_field() -> None:
    request_fields = (
        VisualModelRequest.__dataclass_fields__
    )
    response_fields = (
        VisualModelResponse.__dataclass_fields__
    )

    forbidden_fields = {
        "chain_of_thought",
        "hidden_reasoning",
        "reasoning_trace",
        "internal_reasoning",
    }

    assert forbidden_fields.isdisjoint(
        request_fields
    )
    assert forbidden_fields.isdisjoint(
        response_fields
    )
