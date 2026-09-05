from __future__ import annotations

from threading import Lock
from typing import Any
from uuid import UUID

from engine.backend import get_backend
from engine.models import DataRecord
from engine.query import QueryService


_WRITE_LOCK = Lock()


class DataEngineEvidenceBinding:
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


    def write_record(
        self,
        record: dict[str, Any],
    ) -> None:
        normalized = self._normalize_record(
            record
        )

        with _WRITE_LOCK:
            record_id = self._next_record_id()

            data_record = DataRecord.create(
                id=record_id,
                source=normalized["source"],
                category=normalized["category"],
                data_type=normalized["data_type"],
                value=normalized["value"],
                unit=normalized["unit"],
            )

            stored = data_record.to_dict()

            self.query_service.insert_record(
                stored
            )


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
    def _normalize_record(
        record: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(
            record,
            dict,
        ):
            raise TypeError(
                "Evidence record must be a dictionary."
            )

        required_fields = (
            "id",
            "source",
            "category",
            "data_type",
            "value",
            "unit",
        )

        missing_fields = [
            field
            for field in required_fields
            if field not in record
        ]

        if missing_fields:
            raise ValueError(
                "Evidence record is missing fields: "
                f"{missing_fields}"
            )

        evidence_id = str(
            record["id"]
        ).strip()

        source = str(
            record["source"]
        ).strip()

        category = str(
            record["category"]
        ).strip()

        data_type = str(
            record["data_type"]
        ).strip()

        unit = str(
            record["unit"]
        ).strip()

        value = record["value"]

        if not evidence_id:
            raise ValueError(
                "id cannot be empty."
            )

        if not source:
            raise ValueError(
                "source cannot be empty."
            )

        if not category:
            raise ValueError(
                "category cannot be empty."
            )

        if not data_type:
            raise ValueError(
                "data_type cannot be empty."
            )

        if not unit:
            raise ValueError(
                "unit cannot be empty."
            )

        if not isinstance(
            value,
            dict,
        ):
            raise TypeError(
                "Evidence value must be a dictionary."
            )

        if str(
            value.get(
                "id",
                "",
            )
        ) != evidence_id:
            raise ValueError(
                "Evidence envelope id must match "
                "value['id']."
            )

        return {
            "source": source,
            "category": category,
            "data_type": data_type,
            "value": value,
            "unit": unit,
        }


    def read_entity_record(
        self,
        entity_id: UUID,
    ) -> dict[str, Any] | None:
        wanted_id = str(
            entity_id
        )

        for record in (
            self.query_service
            .get_all_records()
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
                    "id",
                    "",
                )
            ) != wanted_id:
                continue

            data_type = record.get(
                "data_type"
            )

            if not isinstance(
                data_type,
                str,
            ) or not data_type.strip():
                continue

            return {
                "id": wanted_id,
                "source": record.get(
                    "source",
                    "",
                ),
                "category": record.get(
                    "category",
                    "",
                ),
                "data_type": data_type,
                "value": value,
                "unit": record.get(
                    "unit",
                    "",
                ),
            }

        return None


    def query_records(
        self,
        entity_type: str | None,
    ) -> list[dict[str, Any]]:
        records = (
            self.query_service
            .get_all_records()
        )

        results: list[
            dict[str, Any]
        ] = []

        for record in records:
            data_type = record.get(
                "data_type"
            )

            if entity_type is not None:
                if data_type != entity_type:
                    continue

            value = record.get(
                "value"
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            evidence_id = str(
                value.get(
                    "id",
                    "",
                )
            ).strip()

            if not evidence_id:
                continue

            if not isinstance(
                data_type,
                str,
            ) or not data_type.strip():
                continue

            results.append(
                {
                    "id": evidence_id,
                    "source": record.get(
                        "source",
                        "",
                    ),
                    "category": record.get(
                        "category",
                        "",
                    ),
                    "data_type": data_type,
                    "value": value,
                    "unit": record.get(
                        "unit",
                        "",
                    ),
                }
            )

        return results


def build_evidence_repository(
    *,
    query_service: QueryService | None = None,
):
    from engine.evidence.data_engine_repository import (
        PlatformDataEngineRepository,
    )

    binding = DataEngineEvidenceBinding(
        query_service=query_service,
    )

    return PlatformDataEngineRepository(
        write_record=binding.write_record,
        read_entity_record=(
            binding.read_entity_record
        ),
        query_records=binding.query_records,
    )
