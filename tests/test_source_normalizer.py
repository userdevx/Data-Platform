from engine.source_normalizer import (
    normalize_source_record,
    resolve_source_data_type,
)


def test_generic_data_type_is_preserved():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": {
            "state": "ready",
        },
        "unit": "record",
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["data_type"]
        == "runtime_data"
    )

    assert (
        normalized["metadata"][
            "original_data_type"
        ]
        == "runtime_data"
    )


def test_missing_data_type_becomes_unknown_data():
    record = {
        "source": "runtime_device",
        "category": "runtime_category",
        "value": True,
        "unit": "boolean",
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["data_type"]
        == "unknown_data"
    )

    assert (
        normalized["metadata"][
            "original_data_type"
        ]
        == "unknown_data"
    )


def test_resolve_source_data_type_returns_data_type():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "canonical_data",
        "value": 1,
        "unit": "record",
    }

    assert (
        resolve_source_data_type(
            record
        )
        == "canonical_data"
    )

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["data_type"]
        == "canonical_data"
    )


def test_generic_source_is_not_forced_to_device_type():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": 1,
        "unit": "record",
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["source"]
        == "runtime_source"
    )


def test_source_type_metadata_can_override_source():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": 1,
        "unit": "record",
        "metadata": {
            "source_type":
                "configured_source_type",
        },
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["source"]
        == "configured_source_type"
    )

    assert (
        normalized["metadata"][
            "original_source"
        ]
        == "runtime_source"
    )


def test_source_identity_metadata_is_generated():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": 1,
        "unit": "record",
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["source_id"]
        == "src_runtime_source"
    )

    assert (
        normalized["source_label"]
        == "Runtime Source"
    )


def test_custom_source_metadata_is_preserved():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": 1,
        "unit": "record",
        "metadata": {
            "source_type":
                "configured_source",
            "source_id":
                "configured_id",
            "source_label":
                "Configured Label",
        },
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["source"]
        == "configured_source"
    )

    assert (
        normalized["source_id"]
        == "configured_id"
    )

    assert (
        normalized["source_label"]
        == "Configured Label"
    )


def test_missing_type_uses_unknown_data():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "value": 1,
        "unit": "record",
    }

    normalized = normalize_source_record(
        record
    )

    assert (
        normalized["data_type"]
        == "unknown_data"
    )


def test_invalid_metadata_is_replaced_safely():
    record = {
        "source": "runtime_source",
        "category": "runtime_category",
        "data_type": "runtime_data",
        "value": 1,
        "unit": "record",
        "metadata": [],
    }

    normalized = normalize_source_record(
        record
    )

    assert isinstance(
        normalized["metadata"],
        dict,
    )
