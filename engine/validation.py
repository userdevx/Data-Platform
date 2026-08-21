from __future__ import annotations

from typing import Any

from engine.exceptions import ValidationError


REQUIRED_FIELDS = (
    "id",
    "source",
    "category",
    "value",
    "unit",
    "created_at",
    "updated_at",
)

TYPE_FIELDS = (
    "data_type",
    "sensor_type",
)


def validate_required_fields(
    record: dict[str, Any],
) -> None:
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise ValidationError(
                f"Missing required field: {field}"
            )

    if not any(
        field in record
        for field in TYPE_FIELDS
    ):
        raise ValidationError(
            "Missing required field: data_type"
        )


def validate_id(
    record: dict[str, Any],
) -> None:
    if not isinstance(
        record["id"],
        int,
    ):
        raise ValidationError(
            "Field 'id' must be an integer"
        )


def validate_text_field(
    record: dict[str, Any],
    field_name: str,
) -> None:
    value = record.get(
        field_name
    )

    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        raise ValidationError(
            f"Field '{field_name}' "
            "must be a non-empty string"
        )


def validate_category(
    record: dict[str, Any],
) -> None:
    validate_text_field(
        record,
        "category",
    )


def resolve_data_type(
    record: dict[str, Any],
) -> str:
    data_type = record.get(
        "data_type"
    )

    if (
        isinstance(
            data_type,
            str,
        )
        and data_type.strip()
    ):
        return data_type.strip()

    sensor_type = record.get(
        "sensor_type"
    )

    if (
        isinstance(
            sensor_type,
            str,
        )
        and sensor_type.strip()
    ):
        return sensor_type.strip()

    raise ValidationError(
        "Field 'data_type' must be a "
        "non-empty string"
    )


def validate_data_type(
    record: dict[str, Any],
) -> None:
    resolve_data_type(
        record
    )


def validate_value(
    record: dict[str, Any],
) -> None:
    if record["value"] is None:
        raise ValidationError(
            "Field 'value' cannot be empty"
        )


def validate_metadata(
    record: dict[str, Any],
) -> None:
    if (
        "metadata" in record
        and not isinstance(
            record["metadata"],
            dict,
        )
    ):
        raise ValidationError(
            "Field 'metadata' must be "
            "a dictionary"
        )


def validate_record(
    record: dict[str, Any],
) -> bool:
    if not isinstance(
        record,
        dict,
    ):
        raise ValidationError(
            "Record must be a dictionary"
        )

    validate_required_fields(
        record
    )

    validate_id(
        record
    )

    validate_text_field(
        record,
        "source",
    )

    validate_category(
        record
    )

    validate_data_type(
        record
    )

    validate_value(
        record
    )

    validate_text_field(
        record,
        "unit",
    )

    validate_text_field(
        record,
        "created_at",
    )

    validate_text_field(
        record,
        "updated_at",
    )

    validate_metadata(
        record
    )

    return True
