from datetime import datetime


VALID_SOURCE_CATEGORIES = {
    "system",
    "edge_device",
    "sensor_node",
    "camera",
    "application",
    "cloud_service",
    "file_source",
    "artifact_source",
}

REQUIRED_FIELDS = {
    "source",
    "category",
    "sensor_type",
    "value",
    "unit",
}


def is_valid_timestamp(value):
    if value is None:
        return True

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False


def check_required_fields(record):
    missing_fields = []

    for field in REQUIRED_FIELDS:
        if field not in record:
            missing_fields.append(field)

    return missing_fields


def check_source_category(record):
    source = record.get("source")

    if source not in VALID_SOURCE_CATEGORIES:
        return f"Invalid source category: {source}"

    return None


def check_timestamp(record):
    created_at = record.get("created_at")

    if not is_valid_timestamp(created_at):
        return f"Invalid created_at timestamp: {created_at}"

    return None


def check_sensor_value(record):
    sensor_type = record.get("sensor_type")
    value = record.get("value")

    if sensor_type == "pir_motion_sensor":
        if value not in [True, False, 1, 0]:
            return "Invalid PIR motion value. Expected boolean or 0/1."

    if "temperature" in str(sensor_type):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "Invalid temperature value. Expected number."

        if number < -100 or number > 200:
            return "Temperature value outside expected range."

    return None


def check_missing_file(record):
    unit = record.get("unit")
    value = record.get("value")

    if unit != "file_path":
        return None

    if not value:
        return "Missing file path value."

    return None


def check_duplicate_ids(records):
    seen_ids = set()
    duplicate_ids = []

    for record in records:
        record_id = record.get("id")

        if record_id is None:
            continue

        if record_id in seen_ids:
            duplicate_ids.append(record_id)

        seen_ids.add(record_id)

    return duplicate_ids


def validate_data_quality(record):
    errors = []

    missing_fields = check_required_fields(record)

    if missing_fields:
        errors.append(f"Missing required fields: {missing_fields}")

    source_error = check_source_category(record)

    if source_error:
        errors.append(source_error)

    timestamp_error = check_timestamp(record)

    if timestamp_error:
        errors.append(timestamp_error)

    sensor_error = check_sensor_value(record)

    if sensor_error:
        errors.append(sensor_error)

    file_error = check_missing_file(record)

    if file_error:
        errors.append(file_error)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


def validate_dataset_quality(records):
    errors = []

    duplicate_ids = check_duplicate_ids(records)

    if duplicate_ids:
        errors.append(f"Duplicate record ids found: {duplicate_ids}")

    for index, record in enumerate(records):
        result = validate_data_quality(record)

        if not result["valid"]:
            errors.append({
                "record_index": index,
                "record_id": record.get("id"),
                "errors": result["errors"],
            })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "record_count": len(records),
    }
