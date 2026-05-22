from engine.data_quality import (
    validate_data_quality,
    validate_dataset_quality,
)


def valid_motion_record():
    return {
        "id": 1,
        "source": "edge_device",
        "category": "motion",
        "sensor_type": "pir_motion_sensor",
        "value": True,
        "unit": "boolean",
        "created_at": "2026-05-15T18:00:00+00:00",
    }


def test_valid_motion_record_passes_quality():
    result = validate_data_quality(valid_motion_record())

    assert result["valid"] is True
    assert result["errors"] == []


def test_missing_required_field_fails_quality():
    record = valid_motion_record()
    del record["sensor_type"]

    result = validate_data_quality(record)

    assert result["valid"] is False
    assert "Missing required fields" in result["errors"][0]


def test_invalid_source_category_fails_quality():
    record = valid_motion_record()
    record["source"] = "arduino_uno_r4_wifi"

    result = validate_data_quality(record)

    assert result["valid"] is False
    assert "Invalid source category" in result["errors"][0]


def test_invalid_timestamp_fails_quality():
    record = valid_motion_record()
    record["created_at"] = "bad_timestamp"

    result = validate_data_quality(record)

    assert result["valid"] is False
    assert "Invalid created_at timestamp" in result["errors"][0]


def test_invalid_motion_value_fails_quality():
    record = valid_motion_record()
    record["value"] = "motion"

    result = validate_data_quality(record)

    assert result["valid"] is False
    assert "Invalid PIR motion value" in result["errors"][0]


def test_duplicate_ids_fail_dataset_quality():
    records = [
        valid_motion_record(),
        valid_motion_record(),
    ]

    result = validate_dataset_quality(records)

    assert result["valid"] is False
    assert "Duplicate record ids" in result["errors"][0]
