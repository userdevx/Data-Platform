from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Any

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


REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "question",
        "image_base64",
        "media_type",
        "response_schema",
        "source_reference",
        "metadata",
    }
)

REQUIRED_REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "question",
        "image_base64",
        "media_type",
        "response_schema",
    }
)

RESPONSE_FIELDS = frozenset(
    {
        "request_id",
        "provider",
        "model_id",
        "scene_description",
        "entities",
        "relations",
        "visible_text",
        "uncertainty",
        "duration_ms",
        "validation_passed",
        "warnings",
        "metadata",
    }
)

HEALTH_FIELDS = frozenset(
    {
        "available",
        "provider",
        "model_id",
        "message",
        "details",
    }
)


def _require_mapping(
    value: Any,
    *,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VisualModelSerializationError(
            f"{field_name} must be an object."
        )

    return value


def _require_string(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise VisualModelSerializationError(
            f"{field_name} must be text."
        )

    return value


def _require_boolean(
    value: Any,
    *,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise VisualModelSerializationError(
            f"{field_name} must be a boolean."
        )

    return value


def _require_integer(
    value: Any,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise VisualModelSerializationError(
            f"{field_name} must be an integer."
        )

    return value


def _require_string_collection(
    value: Any,
    *,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise VisualModelSerializationError(
            f"{field_name} must be an array."
        )

    result: list[str] = []

    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise VisualModelSerializationError(
                f"{field_name}[{index}] must be text."
            )

        result.append(item)

    return tuple(result)


def _require_mapping_collection(
    value: Any,
    *,
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise VisualModelSerializationError(
            f"{field_name} must be an array."
        )

    result: list[Mapping[str, Any]] = []

    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise VisualModelSerializationError(
                f"{field_name}[{index}] must be an object."
            )

        result.append(dict(item))

    return tuple(result)


def _validate_fields(
    value: Mapping[str, Any],
    *,
    allowed_fields: frozenset[str],
    required_fields: frozenset[str],
    field_name: str,
) -> None:
    received_fields = set(value)

    unknown_fields = (
        received_fields
        - allowed_fields
    )

    if unknown_fields:
        names = ", ".join(
            sorted(unknown_fields)
        )

        raise VisualModelSerializationError(
            f"{field_name} contains unknown fields: {names}"
        )

    missing_fields = (
        required_fields
        - received_fields
    )

    if missing_fields:
        names = ", ".join(
            sorted(missing_fields)
        )

        raise VisualModelSerializationError(
            f"{field_name} is missing required fields: {names}"
        )


def decode_json_payload(
    payload: bytes,
    *,
    maximum_payload_size_bytes: int,
) -> Mapping[str, Any]:
    if maximum_payload_size_bytes < 1:
        raise ValueError(
            "maximum_payload_size_bytes must be positive."
        )

    if not payload:
        raise VisualModelSerializationError(
            "The transport payload is empty."
        )

    if len(payload) > maximum_payload_size_bytes:
        raise VisualModelSerializationError(
            "The transport payload exceeds the maximum size."
        )

    try:
        decoded_text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VisualModelSerializationError(
            "The transport payload must use UTF-8."
        ) from error

    try:
        value = json.loads(decoded_text)
    except json.JSONDecodeError as error:
        raise VisualModelSerializationError(
            "The transport payload is not valid JSON."
        ) from error

    return _require_mapping(
        value,
        field_name="payload",
    )


def encode_json_payload(
    value: Mapping[str, Any],
    *,
    maximum_payload_size_bytes: int,
) -> bytes:
    if maximum_payload_size_bytes < 1:
        raise ValueError(
            "maximum_payload_size_bytes must be positive."
        )

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
    ) as error:
        raise VisualModelSerializationError(
            "The response could not be encoded as JSON."
        ) from error

    if len(encoded) > maximum_payload_size_bytes:
        raise VisualModelSerializationError(
            "The encoded payload exceeds the maximum size."
        )

    return encoded


def request_to_mapping(
    request: VisualModelRequest,
) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "question": request.question,
        "image_base64": base64.b64encode(
            request.image_data
        ).decode("ascii"),
        "media_type": request.media_type,
        "response_schema": dict(
            request.response_schema
        ),
        "source_reference": (
            request.source_reference
        ),
        "metadata": dict(
            request.metadata
        ),
    }


def request_from_mapping(
    value: Mapping[str, Any],
) -> VisualModelRequest:
    mapping = _require_mapping(
        value,
        field_name="request",
    )

    _validate_fields(
        mapping,
        allowed_fields=REQUEST_FIELDS,
        required_fields=REQUIRED_REQUEST_FIELDS,
        field_name="request",
    )

    encoded_image = _require_string(
        mapping["image_base64"],
        field_name="request.image_base64",
    )

    try:
        image_data = base64.b64decode(
            encoded_image,
            validate=True,
        )
    except (
        binascii.Error,
        ValueError,
    ) as error:
        raise VisualModelSerializationError(
            "request.image_base64 is not valid base64."
        ) from error

    source_reference_value = mapping.get(
        "source_reference"
    )

    if (
        source_reference_value is not None
        and not isinstance(
            source_reference_value,
            str,
        )
    ):
        raise VisualModelSerializationError(
            "request.source_reference must be text or null."
        )

    response_schema = _require_mapping(
        mapping["response_schema"],
        field_name="request.response_schema",
    )

    metadata = _require_mapping(
        mapping.get("metadata", {}),
        field_name="request.metadata",
    )

    return VisualModelRequest(
        request_id=_require_string(
            mapping["request_id"],
            field_name="request.request_id",
        ),
        question=_require_string(
            mapping["question"],
            field_name="request.question",
        ),
        image_data=image_data,
        media_type=_require_string(
            mapping["media_type"],
            field_name="request.media_type",
        ),
        response_schema=dict(
            response_schema
        ),
        source_reference=(
            source_reference_value
        ),
        metadata=dict(metadata),
    )


def response_to_mapping(
    response: VisualModelResponse,
) -> dict[str, Any]:
    return response.to_record()


def response_from_mapping(
    value: Mapping[str, Any],
) -> VisualModelResponse:
    mapping = _require_mapping(
        value,
        field_name="response",
    )

    _validate_fields(
        mapping,
        allowed_fields=RESPONSE_FIELDS,
        required_fields=RESPONSE_FIELDS,
        field_name="response",
    )

    metadata = _require_mapping(
        mapping["metadata"],
        field_name="response.metadata",
    )

    return VisualModelResponse(
        request_id=_require_string(
            mapping["request_id"],
            field_name="response.request_id",
        ),
        provider=_require_string(
            mapping["provider"],
            field_name="response.provider",
        ),
        model_id=_require_string(
            mapping["model_id"],
            field_name="response.model_id",
        ),
        scene_description=_require_string(
            mapping["scene_description"],
            field_name="response.scene_description",
        ),
        entities=_require_mapping_collection(
            mapping["entities"],
            field_name="response.entities",
        ),
        relations=_require_mapping_collection(
            mapping["relations"],
            field_name="response.relations",
        ),
        visible_text=_require_string_collection(
            mapping["visible_text"],
            field_name="response.visible_text",
        ),
        uncertainty=_require_string_collection(
            mapping["uncertainty"],
            field_name="response.uncertainty",
        ),
        duration_ms=_require_integer(
            mapping["duration_ms"],
            field_name="response.duration_ms",
        ),
        validation_passed=_require_boolean(
            mapping["validation_passed"],
            field_name="response.validation_passed",
        ),
        warnings=_require_string_collection(
            mapping["warnings"],
            field_name="response.warnings",
        ),
        metadata=dict(metadata),
    )


def health_to_mapping(
    health: VisualRuntimeHealth,
) -> dict[str, Any]:
    return {
        "available": health.available,
        "provider": health.provider,
        "model_id": health.model_id,
        "message": health.message,
        "details": list(
            health.details
        ),
    }


def health_from_mapping(
    value: Mapping[str, Any],
) -> VisualRuntimeHealth:
    mapping = _require_mapping(
        value,
        field_name="health",
    )

    _validate_fields(
        mapping,
        allowed_fields=HEALTH_FIELDS,
        required_fields=HEALTH_FIELDS,
        field_name="health",
    )

    return VisualRuntimeHealth(
        available=_require_boolean(
            mapping["available"],
            field_name="health.available",
        ),
        provider=_require_string(
            mapping["provider"],
            field_name="health.provider",
        ),
        model_id=_require_string(
            mapping["model_id"],
            field_name="health.model_id",
        ),
        message=_require_string(
            mapping["message"],
            field_name="health.message",
        ),
        details=_require_string_collection(
            mapping["details"],
            field_name="health.details",
        ),
    )
