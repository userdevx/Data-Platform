from __future__ import annotations

from threading import Lock
from typing import Any, Protocol

from engine.backend import get_backend
from engine.models import DataRecord
from engine.query import QueryService


_WRITE_LOCK = Lock()


class DataEngineSerializable(Protocol):
    def to_data_engine_record(
        self,
    ) -> dict[str, Any]:
        ...


class MarketIntelligenceDataEngineWriter:
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

    def write(
        self,
        entity: DataEngineSerializable,
    ) -> dict[str, Any]:
        payload = (
            entity.to_data_engine_record()
        )

        return self.write_payload(
            payload
        )

    def write_payload(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = self._normalize_payload(
            payload
        )

        with _WRITE_LOCK:
            record_id = self._next_record_id()

            record = DataRecord.create(
                id=record_id,
                source=normalized["source"],
                category=normalized["category"],
                data_type=normalized["data_type"],
                value=normalized["value"],
                unit=normalized["unit"],
            )

            stored = (
                self.query_service
                .insert_record(
                    record.to_dict()
                )
            )

        return stored

    def _next_record_id(
        self,
    ) -> int:
        records = (
            self.query_service
            .get_all_records()
        )

        existing_ids = [
            record.get("id")
            for record in records
            if isinstance(
                record.get("id"),
                int,
            )
        ]

        if not existing_ids:
            return 1

        return max(
            existing_ids
        ) + 1

    @staticmethod
    def _normalize_payload(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "Data Engine payload "
                "must be a dictionary."
            )

        required_fields = (
            "source",
            "category",
            "data_type",
            "value",
            "unit",
        )

        missing_fields = [
            field
            for field in required_fields
            if field not in payload
        ]

        if missing_fields:
            raise ValueError(
                "Market Intelligence "
                "Data Engine payload "
                "is missing fields: "
                f"{missing_fields}"
            )

        normalized = {
            "source": str(
                payload["source"]
            ).strip(),
            "category": str(
                payload["category"]
            ).strip(),
            "data_type": str(
                payload["data_type"]
            ).strip(),
            "value": payload["value"],
            "unit": str(
                payload["unit"]
            ).strip(),
        }

        for field in (
            "source",
            "category",
            "data_type",
            "unit",
        ):
            if not normalized[field]:
                raise ValueError(
                    f"{field} cannot be empty."
                )

        if normalized["value"] is None:
            raise ValueError(
                "value cannot be empty."
            )

        return normalized
