from __future__ import annotations

from typing import Any


def resolve_source_data_type(
    record: dict[str, Any],
) -> str:
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

    return "unknown_data"


def normalize_source_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(
        record
    )

    metadata_value = normalized.get(
        "metadata",
        {},
    )

    metadata = (
        dict(metadata_value)
        if isinstance(
            metadata_value,
            dict,
        )
        else {}
    )

    original_source = str(
        normalized.get(
            "source",
            "unknown_source",
        )
    ).strip() or "unknown_source"

    original_data_type = (
        resolve_source_data_type(
            normalized
        )
    )

    legacy_sensor_type = (
        normalized.get(
            "sensor_type"
        )
    )

    source_type = metadata.get(
        "source_type"
    )

    if (
        isinstance(source_type, str)
        and source_type.strip()
    ):
        normalized_source = (
            source_type.strip()
        )
    else:
        normalized_source = (
            original_source
        )

    source_id = metadata.get(
        "source_id"
    )

    if (
        not isinstance(
            source_id,
            str,
        )
        or not source_id.strip()
    ):
        source_id = (
            f"src_{original_source}"
        )

    source_label = metadata.get(
        "source_label"
    )

    if (
        not isinstance(
            source_label,
            str,
        )
        or not source_label.strip()
    ):
        source_label = (
            original_source
            .replace(
                "_",
                " ",
            )
            .strip()
            .title()
        )

    normalized[
        "source"
    ] = normalized_source

    normalized[
        "source_id"
    ] = source_id

    normalized[
        "source_label"
    ] = source_label

    normalized[
        "data_type"
    ] = original_data_type

    metadata[
        "original_source"
    ] = original_source

    metadata[
        "original_data_type"
    ] = original_data_type

    if (
        isinstance(
            legacy_sensor_type,
            str,
        )
        and legacy_sensor_type.strip()
    ):
        clean_sensor_type = (
            legacy_sensor_type.strip()
        )

        normalized[
            "sensor_type"
        ] = clean_sensor_type

        metadata[
            "original_sensor_type"
        ] = clean_sensor_type

        sensor_model = metadata.get(
            "sensor_model"
        )

        if (
            not isinstance(
                sensor_model,
                str,
            )
            or not sensor_model.strip()
        ):
            metadata[
                "sensor_model"
            ] = clean_sensor_type

    normalized[
        "metadata"
    ] = metadata

    return normalized
