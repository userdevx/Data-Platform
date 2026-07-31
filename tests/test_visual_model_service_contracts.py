from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from services.visual_model.errors import (
    VisualModelRequestValidationError,
    VisualModelResponseValidationError,
)
from services.visual_model.request_models import (
    VisualModelRequest,
)
from services.visual_model.response_models import (
    VisualModelResponse,
)
from services.visual_model.runtime_protocol import (
    VisualModelRuntime,
    VisualModelRuntimeHealth,
)
from services.visual_model.validation import (
    validate_visual_model_request,
    validate_visual_model_response,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_request(
    **changes: Any,
) -> VisualModelRequest:
    values: dict[str, Any] = {
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
            "additionalProperties": True,
        },
        "source_reference": runtime_value(
            "source"
        ),
        "metadata": {
            "trace_id": runtime_value(
                "trace"
            ),
        },
    }

    values.update(changes)

    return VisualModelRequest(**values)


def build_response(
    request_id: str,
    **changes: Any,
) -> VisualModelResponse:
    values: dict[str, Any] = {
        "request_id": request_id,
        "provider": runtime_value(
            "provider"
        ),
        "model_id": runtime_value(
            "model"
        ),
        "scene_description": runtime_value(
            "scene"
        ),
        "entities": (
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
        "relations": (
            {
                "relation_id": runtime_value(
                    "relation"
                ),
                "source_entity_id": runtime_value(
                    "source-entity"
                ),
                "target_entity_id": runtime_value(
                    "target-entity"
                ),
                "relation": runtime_value(
                    "relation-label"
                ),
                "confidence": 0.8,
            },
        ),
        "visible_text": (
            runtime_value("visible-text"),
        ),
        "uncertainty": (
            runtime_value("uncertainty"),
        ),
        "duration_ms": 1,
        "validation_passed": True,
        "warnings": (),
        "metadata": {
            "trace_id": runtime_value(
                "trace"
            ),
        },
    }

    values.update(changes)

    return VisualModelResponse(**values)


class CompatibleRuntime:
    def health_check(
        self,
    ) -> VisualModelRuntimeHealth:
        return VisualModelRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            status="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        return build_response(
            request.request_id
        )


def test_valid_request_passes() -> None:
    validate_visual_model_request(
        build_request()
    )


def test_request_record_excludes_image_data_by_default() -> None:
    request = build_request()

    record = request.to_record()

    assert "image_data" not in record
    assert (
        record["image_size_bytes"]
        == len(request.image_data)
    )


def test_request_record_can_include_image_data_explicitly() -> None:
    request = build_request()

    record = request.to_record(
        include_image_data=True
    )

    assert (
        record["image_data"]
        == request.image_data
    )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        (
            "request_id",
            "",
            "request_id",
        ),
        (
            "question",
            "   ",
            "question",
        ),
        (
            "image_data",
            b"",
            "image_data",
        ),
        (
            "media_type",
            "application/octet-stream",
            "media_type",
        ),
        (
            "response_schema",
            {},
            "response_schema",
        ),
    ],
)
def test_invalid_request_fields_are_rejected(
    field_name: str,
    invalid_value: Any,
    message: str,
) -> None:
    request = build_request(
        **{
            field_name: invalid_value,
        }
    )

    with pytest.raises(
        VisualModelRequestValidationError,
        match=message,
    ):
        validate_visual_model_request(
            request
        )


def test_request_size_limit_is_enforced() -> None:
    request = build_request(
        image_data=b"runtime-data"
    )

    with pytest.raises(
        VisualModelRequestValidationError,
        match="size limit",
    ):
        validate_visual_model_request(
            request,
            maximum_image_size_bytes=1,
        )


def test_non_json_request_metadata_is_rejected() -> None:
    request = build_request(
        metadata={
            "value": object(),
        }
    )

    with pytest.raises(
        VisualModelRequestValidationError,
        match="JSON-compatible",
    ):
        validate_visual_model_request(
            request
        )


def test_valid_response_passes() -> None:
    request = build_request()

    validate_visual_model_response(
        build_response(
            request.request_id
        ),
        expected_request_id=(
            request.request_id
        ),
    )


def test_response_request_id_must_match() -> None:
    request = build_request()

    with pytest.raises(
        VisualModelResponseValidationError,
        match="does not match",
    ):
        validate_visual_model_response(
            build_response(
                runtime_value(
                    "different-request"
                )
            ),
            expected_request_id=(
                request.request_id
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        (
            "provider",
            "",
            "provider",
        ),
        (
            "model_id",
            "",
            "model_id",
        ),
        (
            "scene_description",
            "",
            "scene_description",
        ),
        (
            "duration_ms",
            -1,
            "duration_ms",
        ),
        (
            "validation_passed",
            "true",
            "validation_passed",
        ),
    ],
)
def test_invalid_response_fields_are_rejected(
    field_name: str,
    invalid_value: Any,
    message: str,
) -> None:
    request = build_request()

    response = build_response(
        request.request_id,
        **{
            field_name: invalid_value,
        },
    )

    with pytest.raises(
        VisualModelResponseValidationError,
        match=message,
    ):
        validate_visual_model_response(
            response
        )


def test_response_entities_must_be_objects() -> None:
    request = build_request()

    response = build_response(
        request.request_id,
        entities=("invalid",),
    )

    with pytest.raises(
        VisualModelResponseValidationError,
        match=r"entities\[0\]",
    ):
        validate_visual_model_response(
            response
        )


def test_response_record_is_json_ready() -> None:
    request = build_request()

    response = build_response(
        request.request_id
    )

    record = response.to_record()

    assert isinstance(
        record["entities"],
        list,
    )

    assert isinstance(
        record["relations"],
        list,
    )

    assert isinstance(
        record["visible_text"],
        list,
    )


def test_runtime_implements_protocol() -> None:
    runtime = CompatibleRuntime()

    assert isinstance(
        runtime,
        VisualModelRuntime,
    )

    request = build_request()

    response = runtime.analyze(
        request
    )

    assert (
        response.request_id
        == request.request_id
    )


def test_runtime_health_contract() -> None:
    health = CompatibleRuntime().health_check()

    assert health.available is True
    assert health.status == "ready"
    assert health.provider
    assert health.model_id
