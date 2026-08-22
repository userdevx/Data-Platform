from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from engine.application.automatic_model_request_action import (
    process_automatic_model_request,
)
from engine.market_intelligence.models import (
    MarketTrend,
    ProductRequirement,
)


ModelRequest = Callable[
    ...,
    dict[str, Any],
]


_REQUIRED_FIELDS = frozenset(
    {
        "category",
        "description",
        "priority",
    }
)


class ProductRequirementGenerator:
    def __init__(
        self,
        *,
        model_request: ModelRequest | None = None,
    ) -> None:
        self.model_request = (
            model_request
            if model_request is not None
            else process_automatic_model_request
        )

    def generate(
        self,
        trends: list[MarketTrend],
    ) -> ProductRequirement:
        validated_trends = (
            self._validate_trends(
                trends
            )
        )

        response = self.model_request(
            question=self._build_prompt(
                validated_trends
            ),
            required_capability=(
                "text_input"
            ),
        )

        payload = self._extract_payload(
            response
        )

        proposal = self._validate_payload(
            payload
        )

        return ProductRequirement.create(
            category=proposal[
                "category"
            ],
            description=proposal[
                "description"
            ],
            priority=proposal[
                "priority"
            ],
            evidence_topics=(
                self._evidence_topics(
                    validated_trends
                )
            ),
            trend_ids=(
                self._trend_ids(
                    validated_trends
                )
            ),
            confidence=(
                self._requirement_confidence(
                    validated_trends
                )
            ),
        )

    @staticmethod
    def _validate_trends(
        trends: list[MarketTrend],
    ) -> list[MarketTrend]:
        if not isinstance(
            trends,
            list,
        ):
            raise TypeError(
                "Requirement generation "
                "requires a list of "
                "MarketTrend objects."
            )

        if not trends:
            raise ValueError(
                "At least one validated "
                "MarketTrend is required."
            )

        validated: list[
            MarketTrend
        ] = []

        for trend in trends:
            if not isinstance(
                trend,
                MarketTrend,
            ):
                raise TypeError(
                    "Requirement generation "
                    "requires MarketTrend "
                    "objects."
                )

            validated.append(
                trend
            )

        return validated

    @staticmethod
    def _build_prompt(
        trends: list[MarketTrend],
    ) -> str:
        evidence = [
            {
                "topic":
                    trend.topic,
                "mention_count":
                    trend.mention_count,
                "sentiment_score":
                    trend.sentiment_score,
                "confidence":
                    trend.confidence,
                "source_count":
                    trend.source_count,
            }
            for trend in trends
        ]

        return (
            "Create one application product "
            "requirement using only the supplied "
            "validated market trends.\n"
            "Do not use outside knowledge.\n"
            "Do not invent evidence.\n"
            "Return exactly one JSON object and "
            "no additional text.\n"
            "The JSON object must contain exactly "
            "these fields:\n"
            "category: non-empty string\n"
            "description: non-empty string\n"
            "priority: integer from 1 to 5\n"
            "Do not return trend IDs, evidence "
            "topics, confidence values, or "
            "provenance fields.\n"
            "\n"
            "Validated trends:\n"
            f"{json.dumps(evidence)}"
        )

    @staticmethod
    def _extract_payload(
        response: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(
            response,
            dict,
        ):
            raise TypeError(
                "Model response must be a "
                "dictionary."
            )

        status = str(
            response.get(
                "status",
                "",
            )
        ).strip().lower()

        if status != "success":
            raise RuntimeError(
                "Requirement generation did "
                "not complete successfully."
            )

        answer = response.get(
            "answer"
        )

        if not isinstance(
            answer,
            str,
        ):
            raise TypeError(
                "Requirement proposal must "
                "be returned as text."
            )

        clean_answer = (
            answer.strip()
        )

        if not clean_answer:
            raise ValueError(
                "Requirement generation "
                "returned an empty answer."
            )

        try:
            payload = json.loads(
                clean_answer
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Requirement proposal must "
                "be valid JSON."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "Requirement proposal JSON "
                "must be an object."
            )

        return payload

    @classmethod
    def _validate_payload(
        cls,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        fields = frozenset(
            payload
        )

        if fields != _REQUIRED_FIELDS:
            missing = sorted(
                _REQUIRED_FIELDS
                - fields
            )

            unexpected = sorted(
                fields
                - _REQUIRED_FIELDS
            )

            raise ValueError(
                "Requirement proposal schema "
                "does not match the required "
                "fields. "
                f"Missing: {missing}. "
                f"Unexpected: {unexpected}."
            )

        return {
            "category":
                cls._require_text(
                    payload["category"],
                    field_name="category",
                ),
            "description":
                cls._require_text(
                    payload["description"],
                    field_name="description",
                ),
            "priority":
                cls._require_priority(
                    payload["priority"]
                ),
        }

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

        clean_value = value.strip()

        if not clean_value:
            raise ValueError(
                f"{field_name} cannot "
                "be empty."
            )

        return clean_value

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

    @staticmethod
    def _evidence_topics(
        trends: list[MarketTrend],
    ) -> list[str]:
        topics: list[str] = []
        seen: set[str] = set()

        for trend in trends:
            topic = (
                trend.topic.strip()
            )

            normalized = (
                topic.casefold()
            )

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            topics.append(
                topic
            )

        return topics

    @staticmethod
    def _trend_ids(
        trends: list[MarketTrend],
    ) -> list[str]:
        identifiers: list[str] = []
        seen: set[str] = set()

        for trend in trends:
            identifier = (
                trend.trend_id.strip()
            )

            if identifier in seen:
                continue

            seen.add(
                identifier
            )

            identifiers.append(
                identifier
            )

        return identifiers

    @staticmethod
    def _requirement_confidence(
        trends: list[MarketTrend],
    ) -> float:
        return sum(
            float(
                trend.confidence
            )
            for trend in trends
        ) / len(
            trends
        )
