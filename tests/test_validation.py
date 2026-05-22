import pytest

from engine.exceptions import ValidationError
from engine.validation import validate_record


def valid_record():
    return {
        "id": 1,
        "source": "system",
        "category": "device_status",
        "sensor_type": "cpu_temperature",
        "value": 52.0,
        "unit": "C",
        "created_at": "2026-05-13T00:00:00+00:00",
        "updated_at": "2026-05-13T00:00:00+00:00",
    }


def test_valid_record_passes_validation():
    record = valid_record()

    assert validate_record(record) is True


def test_missing_required_field_fails_validation():
    record = valid_record()
    del record["sensor_type"]

    with pytest.raises(ValidationError):
        validate_record(record)


def test_invalid_value_type_fails_validation():
    record = valid_record()
    record["value"] = {"bad": "value"}

    with pytest.raises(ValidationError):
        validate_record(record)


def test_camera_record_with_metadata_passes_validation():
    record = {
        "id": 2,
        "source": "system",
        "category": "media",
        "sensor_type": "camera_image",
        "value": "output/camera/test.jpg",
        "unit": "file_path",
        "metadata": {
            "width": 640,
            "height": 480,
            "channels": 3,
        },
        "created_at": "2026-05-13T00:00:00+00:00",
        "updated_at": "2026-05-13T00:00:00+00:00",
    }

    assert validate_record(record) is True
