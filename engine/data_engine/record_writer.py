from __future__ import annotations

from threading import Lock
from typing import Any

from engine.backend import get_backend
from engine.exceptions import (
    DuplicateRecordError,
)
from engine.models import DataRecord
from engine.query import QueryService


_WRITE_LOCK = Lock()


class DataEngineRecordWriter:
    """
    Central write path for Data Engine records created
    by higher-level platform capabilities.

    This class does not own storage. It constructs a
    DataRecord and sends it through QueryService so the
    existing Data Engine validation and configured backend
    remain authoritative.
    """

    def __init__(
        self,
        *,
        query_service: QueryService | None = None,
        max_id_retries: int = 5,
    ) -> None:
        if max_id_retries < 1:
            raise ValueError(
                "max_id_retries must be at least 1."
            )

        self.query_service = (
            query_service
            if query_service is not None
            else QueryService(
                get_backend()
            )
        )

        self.max_id_retries = (
            max_id_retries
        )

    def write(
        self,
        *,
        source: str,
        category: str,
        data_type: str,
        value: Any,
        unit: str,
        sensor_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        normalized_source = (
            self._require_text(
                source,
                "source",
            )
        )

        normalized_category = (
            self._require_text(
                category,
                "category",
            )
        )

        normalized_data_type = (
            self._require_text(
                data_type,
                "data_type",
            )
        )

        normalized_unit = (
            self._require_text(
                unit,
                "unit",
            )
        )

        normalized_sensor_type = (
            None
            if sensor_type is None
            else self._require_text(
                sensor_type,
                "sensor_type",
            )
        )

        normalized_metadata = (
            {}
            if metadata is None
            else self._require_metadata(
                metadata
            )
        )

        if value is None:
            raise ValueError(
                "value cannot be None."
            )

        for attempt in range(
            1,
            self.max_id_retries + 1,
        ):
            with _WRITE_LOCK:
                record_id = (
                    self._next_record_id()
                )

                record = DataRecord.create(
                    id=record_id,
                    source=normalized_source,
                    category=(
                        normalized_category
                    ),
                    data_type=(
                        normalized_data_type
                    ),
                    value=value,
                    unit=normalized_unit,
                )

                stored = record.to_dict()

                if (
                    normalized_sensor_type
                    is not None
                ):
                    stored[
                        "sensor_type"
                    ] = (
                        normalized_sensor_type
                    )

                if normalized_metadata:
                    stored[
                        "metadata"
                    ] = dict(
                        normalized_metadata
                    )

                try:
                    return (
                        self.query_service
                        .insert_record(
                            stored
                        )
                    )

                except DuplicateRecordError:
                    if (
                        attempt
                        >= self.max_id_retries
                    ):
                        raise

        raise RuntimeError(
            "Unable to allocate a Data Engine "
            "record id."
        )

    def _next_record_id(
        self,
    ) -> int:
        records = (
            self.query_service
            .get_all_records()
        )

        ids = [
            record.get(
                "id"
            )
            for record in records
            if isinstance(
                record.get(
                    "id"
                ),
                int,
            )
        ]

        if not ids:
            return 1

        return max(
            ids
        ) + 1

    @staticmethod
    def _require_text(
        value: str,
        field_name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be a string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized

    @staticmethod
    def _require_metadata(
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(
            metadata,
            dict,
        ):
            raise TypeError(
                "metadata must be a dictionary."
            )

        return dict(
            metadata
        )
