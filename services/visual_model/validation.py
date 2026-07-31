from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

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


DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES = (
    15 * 1024 * 1024
)

ALLOWED_MEDIA_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


def _clean_required_text(
    value: str,
    *,
    field_name: str,
    error_type: type[
        VisualModelRequestValidationError
        | VisualModelResponseValidationError
    ],
) -> str:
    if not isinstance(value, str):
        raise error_type(
            f"{field_name} must be text."
        )

    clean_value = " ".join(
        value.split()
    ).strip()

    if not clean_value:
        raise error_type(
            f"{field_name} is required."
        )

    return clean_value


def _validate_json_compatible(
    value: Any,
    *,
    field_name: str,
    error_type: type[
        VisualModelRequestValidationError
        | VisualModelResponseValidationError
    ],
) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as error:
        raise error_type(
            f"{field_name} must be JSON-compatible."
        ) from error


def _validate_mapping_collection(
    values: tuple[
        dict[str, Any],
        ...,
    ],
    *,
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise VisualModelResponseValidationError(
            f"{field_name} must be a tuple."
        )

    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise VisualModelResponseValidationError(
                f"{field_name}[{index}] must be an object."
            )

        _validate_json_compatible(
            dict(value),
            field_name=(
                f"{field_name}[{index}]"
            ),
            error_type=(
                VisualModelResponseValidationError
            ),
        )


def _validate_text_collection(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise VisualModelResponseValidationError(
            f"{field_name} must be a tuple."
        )

    for index, value in enumerate(values):
        _clean_required_text(
            value,
            field_name=(
                f"{field_name}[{index}]"
            ),
            error_type=(
                VisualModelResponseValidationError
            ),
        )


def validate_visual_model_request(
    request: VisualModelRequest,
    *,
    maximum_image_size_bytes: int = (
        DEFAULT_MAXIMUM_IMAGE_SIZE_BYTES
    ),
    allowed_media_types: frozenset[str] = (
        ALLOWED_MEDIA_TYPES
    ),
) -> None:
    _clean_required_text(
        request.request_id,
        field_name="request_id",
        error_type=(
            VisualModelRequestValidationError
        ),
    )

    _clean_required_text(
        request.question,
        field_name="question",
        error_type=(
            VisualModelRequestValidationError
        ),
    )

    if not isinstance(
        request.image_data,
        bytes,
    ):
        raise VisualModelRequestValidationError(
            "image_data must contain bytes."
        )

    if not request.image_data:
        raise VisualModelRequestValidationError(
            "image_data cannot be empty."
        )

    if maximum_image_size_bytes < 1:
        raise VisualModelRequestValidationError(
            "maximum_image_size_bytes must be positive."
        )

    if (
        len(request.image_data)
        > maximum_image_size_bytes
    ):
        raise VisualModelRequestValidationError(
            "image_data exceeds the configured size limit."
        )

    clean_media_type = _clean_required_text(
        request.media_type,
        field_name="media_type",
        error_type=(
            VisualModelRequestValidationError
        ),
    ).lower()

    if clean_media_type not in allowed_media_types:
        raise VisualModelRequestValidationError(
            "media_type is not allowed."
        )

    if not isinstance(
        request.response_schema,
        dict,
    ):
        raise VisualModelRequestValidationError(
            "response_schema must be an object."
        )

    if not request.response_schema:
        raise VisualModelRequestValidationError(
            "response_schema cannot be empty."
        )

    _validate_json_compatible(
        request.response_schema,
        field_name="response_schema",
        error_type=(
            VisualModelRequestValidationError
        ),
    )

    if request.source_reference is not None:
        _clean_required_text(
            request.source_reference,
            field_name="source_reference",
            error_type=(
                VisualModelRequestValidationError
            ),
        )

    if not isinstance(
        request.metadata,
        dict,
    ):
        raise VisualModelRequestValidationError(
            "metadata must be an object."
        )

    _validate_json_compatible(
        request.metadata,
        field_name="metadata",
        error_type=(
            VisualModelRequestValidationError
        ),
    )


def validate_visual_model_response(
    response: VisualModelResponse,
    *,
    expected_request_id: str | None = None,
) -> None:
    request_id = _clean_required_text(
        response.request_id,
        field_name="request_id",
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    if (
        expected_request_id is not None
        and request_id != expected_request_id
    ):
        raise VisualModelResponseValidationError(
            "response request_id does not match "
            "the originating request."
        )

    _clean_required_text(
        response.provider,
        field_name="provider",
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    _clean_required_text(
        response.model_id,
        field_name="model_id",
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    _clean_required_text(
        response.scene_description,
        field_name="scene_description",
        error_type=(
            VisualModelResponseValidationError
        ),
    )

    _validate_mapping_collection(
        response.entities,
        field_name="entities",
    )

    _validate_mapping_collection(
        response.relations,
        field_name="relations",
    )

    _validate_text_collection(
        response.visible_text,
        field_name="visible_text",
    )

    _validate_text_collection(
        response.uncertainty,
        field_name="uncertainty",
    )

    _validate_text_collection(
        response.warnings,
        field_name="warnings",
    )

    if (
        not isinstance(response.duration_ms, int)
        or isinstance(response.duration_ms, bool)
        or response.duration_ms < 0
    ):
        raise VisualModelResponseValidationError(
            "duration_ms must be a non-negative integer."
        )

    if not isinstance(
        response.validation_passed,
        bool,
    ):
        raise VisualModelResponseValidationError(
            "validation_passed must be boolean."
        )

    if not isinstance(
        response.metadata,
        dict,
    ):
        raise VisualModelResponseValidationError(
            "metadata must be an object."
        )

    _validate_json_compatible(
        response.metadata,
        field_name="metadata",
        error_type=(
            VisualModelResponseValidationError
        ),
    )
