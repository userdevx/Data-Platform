from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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


DEFAULT_ALLOWED_MEDIA_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)

MAXIMUM_REQUEST_ID_LENGTH = 200
MAXIMUM_QUESTION_LENGTH = 8_000
MAXIMUM_PROVIDER_LENGTH = 200
MAXIMUM_MODEL_ID_LENGTH = 500
MAXIMUM_DESCRIPTION_LENGTH = 50_000
MAXIMUM_COLLECTION_ITEMS = 10_000


def _require_text(
    value: str,
    *,
    field_name: str,
    maximum_length: int,
    error_type: type[ValueError],
) -> None:
    if not value:
        raise error_type(
            f"{field_name} is required."
        )

    if len(value) > maximum_length:
        raise error_type(
            f"{field_name} exceeds its maximum length."
        )


def _validate_mapping_collection(
    values: tuple[
        Mapping[str, Any],
        ...,
    ],
    *,
    field_name: str,
) -> None:
    if len(values) > MAXIMUM_COLLECTION_ITEMS:
        raise VisualModelResponseValidationError(
            f"{field_name} contains too many items."
        )

    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise VisualModelResponseValidationError(
                f"{field_name}[{index}] must be an object."
            )


def validate_visual_model_request(
    request: VisualModelRequest,
    *,
    maximum_image_size_bytes: int,
    allowed_media_types: frozenset[str] = (
        DEFAULT_ALLOWED_MEDIA_TYPES
    ),
) -> None:
    if maximum_image_size_bytes < 1:
        raise ValueError(
            "maximum_image_size_bytes must be positive."
        )

    _require_text(
        request.request_id,
        field_name="request_id",
        maximum_length=MAXIMUM_REQUEST_ID_LENGTH,
        error_type=(
            VisualModelRequestValidationError
        ),
    )

    _require_text(
        request.question,
        field_name="question",
        maximum_length=MAXIMUM_QUESTION_LENGTH,
        error_type=(
            VisualModelRequestValidationError
        ),
    )

    if not request.image_data:
        raise VisualModelRequestValidationError(
            "image_data is required."
        )

    if (
        request.image_size_bytes
        > maximum_image_size_bytes
    ):
        raise VisualModelRequestValidationError(
            "image_data exceeds the maximum allowed size."
        )

    if request.media_type not in allowed_media_types:
        raise VisualModelRequestValidationError(
            "media_type is not allowed."
        )

    if not request.response_schema:
        raise VisualModelRequestValidationError(
            "response_schema is required."
        )

    if not isinstance(
        request.response_schema,
        Mapping,
    ):
        raise VisualModelRequestValidationError(
            "response_schema must be an object."
        )

    if not isinstance(
        request.metadata,
        Mapping,
    ):
        raise VisualModelRequestValidationError(
            "metadata must be an object."
        )


def validate_visual_model_response(
    response: VisualModelResponse,
    *,
    expected_request_id: str,
) -> None:
    _require_text(
        response.request_id,
        field_name="request_id",
        maximum_length=MAXIMUM_REQUEST_ID_LENGTH,
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    if response.request_id != expected_request_id:
        raise VisualModelResponseValidationError(
            "response request_id does not match the request."
        )

    _require_text(
        response.provider,
        field_name="provider",
        maximum_length=MAXIMUM_PROVIDER_LENGTH,
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    _require_text(
        response.model_id,
        field_name="model_id",
        maximum_length=MAXIMUM_MODEL_ID_LENGTH,
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    if (
        len(response.scene_description)
        > MAXIMUM_DESCRIPTION_LENGTH
    ):
        raise VisualModelResponseValidationError(
            "scene_description exceeds its maximum length."
        )

    if response.duration_ms < 0:
        raise VisualModelResponseValidationError(
            "duration_ms cannot be negative."
        )

    _validate_mapping_collection(
        response.entities,
        field_name="entities",
    )
    _validate_mapping_collection(
        response.relations,
        field_name="relations",
    )

    if (
        len(response.visible_text)
        > MAXIMUM_COLLECTION_ITEMS
    ):
        raise VisualModelResponseValidationError(
            "visible_text contains too many items."
        )

    if (
        len(response.uncertainty)
        > MAXIMUM_COLLECTION_ITEMS
    ):
        raise VisualModelResponseValidationError(
            "uncertainty contains too many items."
        )

    if (
        len(response.warnings)
        > MAXIMUM_COLLECTION_ITEMS
    ):
        raise VisualModelResponseValidationError(
            "warnings contains too many items."
        )

    if not isinstance(
        response.metadata,
        Mapping,
    ):
        raise VisualModelResponseValidationError(
            "metadata must be an object."
        )
