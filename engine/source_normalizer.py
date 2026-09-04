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

    normalized[
        "metadata"
    ] = metadata

    return normalized
