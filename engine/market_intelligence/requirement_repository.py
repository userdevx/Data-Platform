from __future__ import annotations

from typing import Any

from engine.backend import get_backend
from engine.market_intelligence.data_engine_writer import (
    MarketIntelligenceDataEngineWriter,
)
from engine.market_intelligence.models import (
    ProductRequirement,
)
from engine.query import QueryService


_REQUIREMENT_SOURCE = "product_intelligence"
_REQUIREMENT_CATEGORY = "application_requirement"
_REQUIREMENT_UNIT = "requirement"


class ProductRequirementRepository:
    def __init__(
        self,
        *,
        query_service: QueryService | None = None,
        writer: (
            MarketIntelligenceDataEngineWriter
            | None
        ) = None,
    ) -> None:
        self.query_service = (
            query_service
            if query_service is not None
            else QueryService(
                get_backend()
            )
        )

        self.writer = (
            writer
            if writer is not None
            else MarketIntelligenceDataEngineWriter(
                query_service=self.query_service
            )
        )

    def store(
        self,
        requirement: ProductRequirement,
    ) -> dict[str, Any]:
        if not isinstance(
            requirement,
            ProductRequirement,
        ):
            raise TypeError(
                "Requirement repository "
                "can only store "
                "ProductRequirement objects."
            )

        return self.writer.write(
            requirement
        )

    def get_all(
        self,
    ) -> list[ProductRequirement]:
        requirements: list[
            ProductRequirement
        ] = []

        for record in (
            self.query_service
            .get_all_records()
        ):
            if not self._is_requirement_record(
                record
            ):
                continue

            requirements.append(
                self._from_record(
                    record
                )
            )

        return requirements

    def get_by_requirement_id(
        self,
        requirement_id: str,
    ) -> ProductRequirement | None:
        normalized_id = (
            self._require_text(
                requirement_id,
                field_name="requirement_id",
            )
        )

        for requirement in self.get_all():
            if (
                requirement.requirement_id
                == normalized_id
            ):
                return requirement

        return None

    @staticmethod
    def _is_requirement_record(
        record: dict[str, Any],
    ) -> bool:
        if not isinstance(
            record,
            dict,
        ):
            return False

        return (
            record.get("source")
            == _REQUIREMENT_SOURCE
            and record.get("category")
            == _REQUIREMENT_CATEGORY
            and record.get("unit")
            == _REQUIREMENT_UNIT
        )

    @classmethod
    def _from_record(
        cls,
        record: dict[str, Any],
    ) -> ProductRequirement:
        value = record.get(
            "value"
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                "Stored requirement value "
                "must be a dictionary."
            )

        required_value_fields = {
            "requirement_id",
            "description",
            "priority",
            "evidence_topics",
            "trend_ids",
            "confidence",
            "created_at",
        }

        missing_fields = sorted(
            required_value_fields
            - set(value)
        )

        if missing_fields:
            raise ValueError(
                "Stored requirement is "
                "missing fields: "
                f"{missing_fields}"
            )

        category = cls._require_text(
            record.get(
                "data_type"
            ),
            field_name="data_type",
        )

        requirement_id = (
            cls._require_text(
                value[
                    "requirement_id"
                ],
                field_name="requirement_id",
            )
        )

        description = cls._require_text(
            value[
                "description"
            ],
            field_name="description",
        )

        priority = cls._require_priority(
            value[
                "priority"
            ]
        )

        evidence_topics = (
            cls._require_text_list(
                value[
                    "evidence_topics"
                ],
                field_name="evidence_topics",
            )
        )

        trend_ids = (
            cls._require_text_list(
                value[
                    "trend_ids"
                ],
                field_name="trend_ids",
            )
        )

        confidence = (
            cls._require_confidence(
                value[
                    "confidence"
                ]
            )
        )

        created_at = (
            cls._require_text(
                value[
                    "created_at"
                ],
                field_name="created_at",
            )
        )

        return ProductRequirement(
            requirement_id=(
                requirement_id
            ),
            category=category,
            description=description,
            priority=priority,
            evidence_topics=(
                evidence_topics
            ),
            trend_ids=trend_ids,
            confidence=confidence,
            created_at=created_at,
        )

    @staticmethod
    def _require_text(
        value: Any,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be "
                "a string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot "
                "be empty."
            )

        return normalized

    @staticmethod
    def _require_priority(
        value: Any,
    ) -> int:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                "priority must be an integer."
            )

        if not 1 <= value <= 5:
            raise ValueError(
                "priority must be between "
                "1 and 5."
            )

        return value

    @classmethod
    def _require_text_list(
        cls,
        value: Any,
        *,
        field_name: str,
    ) -> list[str]:
        if not isinstance(
            value,
            list,
        ):
            raise TypeError(
                f"{field_name} must be "
                "a list."
            )

        return [
            cls._require_text(
                item,
                field_name=field_name,
            )
            for item in value
        ]

    @staticmethod
    def _require_confidence(
        value: Any,
    ) -> float:
        if (
            not isinstance(
                value,
                (int, float),
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                "confidence must be numeric."
            )

        normalized = float(
            value
        )

        if not 0.0 <= normalized <= 1.0:
            raise ValueError(
                "confidence must be between "
                "0 and 1."
            )

        return normalized
