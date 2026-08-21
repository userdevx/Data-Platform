from __future__ import annotations

from datetime import datetime
from typing import Any


REQUIRED_FIELDS = (
    "source",
    "category",
    "value",
    "unit",
)

TYPE_FIELDS = (
    "data_type",
    "sensor_type",
)


def resolve_quality_data_type(
    record: dict[str, Any],
) -> str | None:
    data_type = record.get(
        "data_type"
    )

    if (
        isinstance(data_type, str)
        and data_type.strip()
    ):
        return data_type.strip()

    sensor_type = record.get(
        "sensor_type"
    )

    if (
        isinstance(sensor_type, str)
        and sensor_type.strip()
    ):
        return sensor_type.strip()

    return None


def is_valid_timestamp(
    value: Any,
) -> bool:
    if value is None:
        return True

    if not isinstance(
        value,
        str,
    ):
        return False

    try:
        datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
        return True
    except ValueError:
        return False


def check_required_fields(
    record: dict[str, Any],
) -> list[str]:
    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in record
    ]

    if not any(
        field in record
        for field in TYPE_FIELDS
    ):
        missing_fields.append(
            "data_type"
        )

    return missing_fields


def check_text_fields(
    record: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for field_name in (
        "source",
        "category",
        "unit",
    ):
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
            errors.append(
                f"Invalid {field_name}. "
                "Expected a non-empty string."
            )

    return errors


def check_data_type(
    record: dict[str, Any],
) -> str | None:
    data_type = resolve_quality_data_type(
        record
    )

    if data_type is None:
        return (
            "Invalid data_type. "
            "Expected a non-empty string."
        )

    return None


def check_timestamp(
    record: dict[str, Any],
) -> str | None:
    created_at = record.get(
        "created_at"
    )

    if not is_valid_timestamp(
        created_at
    ):
        return (
            "Invalid created_at timestamp: "
            f"{created_at}"
        )

    return None


def check_type_specific_value(
    record: dict[str, Any],
) -> str | None:
    data_type = resolve_quality_data_type(
        record
    )

    value = record.get(
        "value"
    )

    if data_type == "pir_motion_sensor":
        if value not in (
            True,
            False,
            1,
            0,
        ):
            return (
                "Invalid PIR motion value. "
                "Expected boolean or 0/1."
            )

    if (
        data_type is not None
        and "temperature"
        in data_type.casefold()
    ):
        try:
            number = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return (
                "Invalid temperature value. "
                "Expected number."
            )

        if (
            number < -100
            or number > 200
        ):
            return (
                "Temperature value outside "
                "expected range."
            )

    return None


def check_missing_file(
    record: dict[str, Any],
) -> str | None:
    unit = record.get(
        "unit"
    )

    value = record.get(
        "value"
    )

    if unit != "file_path":
        return None

    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        return (
            "Missing file path value."
        )

    return None


def check_duplicate_ids(
    records: list[dict[str, Any]],
) -> list[Any]:
    seen_ids: set[Any] = set()
    duplicate_ids: list[Any] = []

    for record in records:
        record_id = record.get(
            "id"
        )

        if record_id is None:
            continue

        if record_id in seen_ids:
            duplicate_ids.append(
                record_id
            )

        seen_ids.add(
            record_id
        )

    return duplicate_ids


def validate_data_quality(
    record: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []

    if not isinstance(
        record,
        dict,
    ):
        return {
            "valid": False,
            "errors": [
                "Record must be a dictionary."
            ],
        }

    missing_fields = check_required_fields(
        record
    )

    if missing_fields:
        errors.append(
            "Missing required fields: "
            f"{missing_fields}"
        )

    text_errors = check_text_fields(
        record
    )

    errors.extend(
        text_errors
    )

    data_type_error = check_data_type(
        record
    )

    if data_type_error:
        errors.append(
            data_type_error
        )

    timestamp_error = check_timestamp(
        record
    )

    if timestamp_error:
        errors.append(
            timestamp_error
        )

    value_error = (
        check_type_specific_value(
            record
        )
    )

    if value_error:
        errors.append(
            value_error
        )

    file_error = check_missing_file(
        record
    )

    if file_error:
        errors.append(
            file_error
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


def validate_dataset_quality(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[Any] = []

    duplicate_ids = check_duplicate_ids(
        records
    )

    if duplicate_ids:
        errors.append(
            "Duplicate record ids found: "
            f"{duplicate_ids}"
        )

    for index, record in enumerate(
        records
    ):
        result = validate_data_quality(
            record
        )

        if not result["valid"]:
            errors.append(
                {
                    "record_index": index,
                    "record_id": record.get(
                        "id"
                    ),
                    "errors": result[
                        "errors"
                    ],
                }
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "record_count": len(
            records
        ),
    }
