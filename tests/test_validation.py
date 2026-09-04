import pytest

from engine.exceptions import ValidationError
from engine.validation import (
    resolve_data_type,
    validate_record,
)


def valid_generic_record():
    return {
        "id": 1,
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": 52.0,
        "unit": "runtime_unit",
        "created_at": "2026-05-13T00:00:00+00:00",
        "updated_at": "2026-05-13T00:00:00+00:00",
    }


def test_generic_data_type_record_passes_validation():
    assert validate_record(
        valid_generic_record()
    ) is True


def test_resolve_data_type_returns_current_data_type():
    record = valid_generic_record()

    assert (
        resolve_data_type(record)
        == "runtime_data"
    )


def test_missing_data_type_fails_validation():
    record = valid_generic_record()
    del record["data_type"]

    with pytest.raises(
        ValidationError,
        match="Missing required field: data_type",
    ):
        validate_record(record)


def test_structured_dictionary_value_passes_validation():
    record = valid_generic_record()

    record["value"] = {
        "topic": "runtime_topic",
        "confidence": 0.84,
        "evidence": [
            "record-a",
            "record-b",
        ],
    }

    assert validate_record(record) is True


def test_structured_list_value_passes_validation():
    record = valid_generic_record()

    record["value"] = [
        {
            "metric": "runtime_metric",
            "value": 1,
        }
    ]

    assert validate_record(record) is True


def test_boolean_value_passes_validation():
    record = valid_generic_record()
    record["value"] = True

    assert validate_record(record) is True


def test_none_value_fails_validation():
    record = valid_generic_record()
    record["value"] = None

    with pytest.raises(
        ValidationError
    ):
        validate_record(record)


def test_generic_category_passes_validation():
    record = valid_generic_record()
    record["category"] = "new_runtime_category"

    assert validate_record(record) is True


def test_empty_category_fails_validation():
    record = valid_generic_record()
    record["category"] = "   "

    with pytest.raises(
        ValidationError
    ):
        validate_record(record)


def test_metadata_dictionary_passes_validation():
    record = valid_generic_record()

    record["metadata"] = {
        "runtime_key": "runtime_value",
    }

    assert validate_record(record) is True


def test_non_dictionary_metadata_fails_validation():
    record = valid_generic_record()
    record["metadata"] = []

    with pytest.raises(
        ValidationError
    ):
        validate_record(record)


def test_invalid_id_fails_validation():
    record = valid_generic_record()
    record["id"] = "1"

    with pytest.raises(
        ValidationError
    ):
        validate_record(record)
