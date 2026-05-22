from engine.exceptions import ValidationError


REQUIRED_FIELDS = [
    "id",
    "source",
    "category",
    "sensor_type",
    "value",
    "unit",
    "created_at",
    "updated_at",
]


VALID_CATEGORIES = [
    "device_status",
    "media",
    "system",
    "network",
    "storage",
]


def validate_required_fields(record):
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise ValidationError(f"Missing required field: {field}")


def validate_id(record):
    if not isinstance(record["id"], int):
        raise ValidationError("Field 'id' must be an integer")


def validate_text_field(record, field_name):
    if not isinstance(record[field_name], str) or not record[field_name].strip():
        raise ValidationError(f"Field '{field_name}' must be a non-empty string")


def validate_category(record):
    validate_text_field(record, "category")

    if record["category"] not in VALID_CATEGORIES:
        raise ValidationError(
            f"Invalid category '{record['category']}'. "
            f"Allowed categories: {VALID_CATEGORIES}"
        )


def validate_value(record):
    if not isinstance(record["value"], (int, float, str)):
        raise ValidationError("Field 'value' must be a number or string")


def validate_metadata(record):
    if "metadata" in record and not isinstance(record["metadata"], dict):
        raise ValidationError("Field 'metadata' must be a dictionary")


def validate_record(record):
    validate_required_fields(record)

    validate_id(record)
    validate_text_field(record, "source")
    validate_category(record)
    validate_text_field(record, "sensor_type")
    validate_value(record)
    validate_text_field(record, "unit")
    validate_text_field(record, "created_at")
    validate_text_field(record, "updated_at")
    validate_metadata(record)

    return True
