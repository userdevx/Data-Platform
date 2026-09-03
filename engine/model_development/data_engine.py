from __future__ import annotations

from typing import Any

from engine.backend import get_backend
from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.query import QueryService


ALLOWED_TRAINING_EVIDENCE_TYPES = frozenset(
    {
        "normalized_information",
        "analysis",
        "validated_trend",
    }
)


class ModelDevelopmentDataEngine:
    """
    Data Engine access boundary for model-development
    lifecycle records.

    This is not a separate training database.

    Writes continue through the shared
    DataEngineRecordWriter and QueryService.
    """

    SOURCE = "model_development"

    # Legacy physical compatibility field required by
    # the current DataRecord envelope.
    CATEGORY = "model_development"

    def __init__(
        self,
        *,
        query_service: QueryService | None = None,
    ) -> None:
        self.query_service = (
            query_service
            if query_service is not None
            else QueryService(
                get_backend()
            )
        )

        self.writer = DataEngineRecordWriter(
            query_service=self.query_service
        )

    def write(
        self,
        *,
        data_type: str,
        value: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(
            value,
            dict,
        ):
            raise TypeError(
                "value must be a dictionary."
            )

        return self.writer.write(
            source=self.SOURCE,
            category=self.CATEGORY,
            data_type=data_type,
            sensor_type=data_type,
            value=value,
            unit="record",
            metadata=metadata,
        )

    def get_record(
        self,
        record_id: int,
    ) -> dict[str, Any]:
        if not isinstance(
            record_id,
            int,
        ):
            raise TypeError(
                "record_id must be an integer."
            )

        return (
            self.query_service
            .get_record_by_id(
                record_id
            )
        )

    def records(
        self,
        *,
        data_type: str | None = None,
    ) -> list[dict[str, Any]]:
        records = (
            self.query_service
            .get_all_records()
        )

        model_records = [
            record
            for record in records
            if (
                isinstance(
                    record,
                    dict,
                )
                and record.get(
                    "source"
                )
                == self.SOURCE
                and record.get(
                    "category"
                )
                == self.CATEGORY
            )
        ]

        if data_type is None:
            return model_records

        return [
            record
            for record in model_records
            if record.get(
                "data_type"
            )
            == data_type
        ]

    def find_model_value(
        self,
        *,
        data_type: str,
        field_name: str,
        field_value: object,
    ) -> dict[str, Any] | None:
        wanted = str(
            field_value
        )

        for record in self.records(
            data_type=data_type
        ):
            value = record.get(
                "value"
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            if str(
                value.get(
                    field_name,
                    "",
                )
            ) == wanted:
                return record

        return None

    def find_evidence_record(
        self,
        evidence_id: object,
    ) -> dict[str, Any] | None:
        """
        Resolve a training Evidence UUID only from the
        explicitly permitted Evidence entity types.

        Ordinary runtime records, raw information,
        model-development records, and unrelated Data
        Engine values cannot satisfy this lookup.
        """

        wanted = str(
            evidence_id
        ).strip()

        if not wanted:
            return None

        for record in (
            self.query_service
            .get_all_records()
        ):
            if not isinstance(
                record,
                dict,
            ):
                continue

            if (
                record.get(
                    "data_type"
                )
                != "structured_knowledge"
            ):
                continue

            if (
                record.get(
                    "sensor_type"
                )
                not in
                ALLOWED_TRAINING_EVIDENCE_TYPES
            ):
                continue

            value = record.get(
                "value"
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            if str(
                value.get(
                    "id",
                    "",
                )
            ) == wanted:
                return record

        return None
