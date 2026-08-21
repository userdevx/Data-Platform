from engine.data_quality import (
    resolve_quality_data_type,
    validate_data_quality,
    validate_dataset_quality,
)


def valid_generic_record():
    return {
        "id": 1,
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": {
            "state": "ready",
        },
        "unit": "record",
        "created_at": (
            "2026-05-15T18:00:00+00:00"
        ),
    }


def valid_legacy_motion_record():
    return {
        "id": 2,
        "source": "runtime_source",
        "category": "motion",
        "sensor_type": "pir_motion_sensor",
        "value": True,
        "unit": "boolean",
        "created_at": (
            "2026-05-15T18:00:00+00:00"
        ),
    }


def test_generic_record_passes_quality():
    result = validate_data_quality(
        valid_generic_record()
    )

    assert result["valid"] is True
    assert result["errors"] == []


def test_legacy_sensor_type_remains_compatible():
    result = validate_data_quality(
        valid_legacy_motion_record()
    )

    assert result["valid"] is True


def test_data_type_is_preferred():
    record = valid_generic_record()

    record["sensor_type"] = (
        "legacy_runtime_data"
    )

    assert (
        resolve_quality_data_type(
            record
        )
        == "runtime_data"
    )


def test_missing_type_field_fails_quality():
    record = valid_generic_record()

    del record["data_type"]

    result = validate_data_quality(
        record
    )

    assert result["valid"] is False

    assert any(
        "Missing required fields"
        in error
        for error in result["errors"]
    )


def test_generic_source_passes_quality():
    record = valid_generic_record()

    record["source"] = (
        "new_runtime_source"
    )

    result = validate_data_quality(
        record
    )

    assert result["valid"] is True


def test_empty_source_fails_quality():
    record = valid_generic_record()

    record["source"] = "   "

    result = validate_data_quality(
        record
    )

    assert result["valid"] is False

    assert any(
        "Invalid source"
        in error
        for error in result["errors"]
    )


def test_invalid_timestamp_fails_quality():
    record = valid_generic_record()

    record["created_at"] = (
        "invalid_timestamp"
    )

    result = validate_data_quality(
        record
    )

    assert result["valid"] is False

    assert any(
        "Invalid created_at timestamp"
        in error
        for error in result["errors"]
    )


def test_invalid_motion_value_fails_quality():
    record = (
        valid_legacy_motion_record()
    )

    record["value"] = "invalid"

    result = validate_data_quality(
        record
    )

    assert result["valid"] is False

    assert any(
        "Invalid PIR motion value"
        in error
        for error in result["errors"]
    )


def test_temperature_value_is_checked():
    record = valid_generic_record()

    record["data_type"] = (
        "temperature_measurement"
    )

    record["value"] = 25.5
    record["unit"] = "temperature_unit"

    result = validate_data_quality(
        record
    )

    assert result["valid"] is True


def test_invalid_temperature_value_fails():
    record = valid_generic_record()

    record["data_type"] = (
        "temperature_measurement"
    )

    record["value"] = "invalid"
    record["unit"] = "temperature_unit"

    result = validate_data_quality(
        record
    )

    assert result["valid"] is False

    assert any(
        "Invalid temperature value"
        in error
        for error in result["errors"]
    )


def test_structured_value_passes_quality():
    record = valid_generic_record()

    record["value"] = {
        "topic": "runtime_topic",
        "confidence": 0.91,
        "evidence": [
            "record-a",
            "record-b",
        ],
    }

    result = validate_data_quality(
        record
    )

    assert result["valid"] is True


def test_missing_file_path_fails_quality():
    record = valid_generic_record()

    record["unit"] = "file_path"
    record["value"] = ""

    result = validate_data_quality(
        record
    )

    assert result["valid"] is False

    assert any(
        "Missing file path value"
        in error
        for error in result["errors"]
    )


def test_duplicate_ids_fail_dataset_quality():
    first = valid_generic_record()
    second = valid_generic_record()

    result = validate_dataset_quality(
        [
            first,
            second,
        ]
    )

    assert result["valid"] is False

    assert any(
        "Duplicate record ids"
        in str(error)
        for error in result["errors"]
    )


def test_unique_ids_pass_dataset_quality():
    first = valid_generic_record()

    second = valid_generic_record()
    second["id"] = 2

    result = validate_dataset_quality(
        [
            first,
            second,
        ]
    )

    assert result["valid"] is True
    assert result["record_count"] == 2
