from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from engine.application.automatic_model_request_action import (
    process_automatic_model_request,
)
from engine.market_intelligence.models import (
    PublicContentRecord,
    SentimentAnalysis,
)


ModelRequest = Callable[
    ...,
    dict[str, Any],
]


_REQUIRED_FIELDS = frozenset(
    {
        "sentiment",
        "sentiment_score",
        "topics",
        "features",
        "complaints",
        "requests",
        "confidence",
    }
)


class MarketIntelligenceAnalyzer:
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

    def analyze(
        self,
        record: PublicContentRecord,
    ) -> SentimentAnalysis:
        if not isinstance(
            record,
            PublicContentRecord,
        ):
            raise TypeError(
                "Analysis requires a "
                "PublicContentRecord."
            )

        retrieved_text = (
            record.retrieved_text.strip()
        )

        if not retrieved_text:
            raise ValueError(
                "Public content cannot be "
                "empty before analysis."
            )

        response = self.model_request(
            question=self._build_prompt(
                retrieved_text
            ),
            required_capability=(
                "text_input"
            ),
        )

        payload = self._extract_payload(
            response
        )

        validated = self._validate_payload(
            payload
        )

        return SentimentAnalysis.create(
            record_id=record.record_id,
            source_name=record.source_name,
            sentiment=validated[
                "sentiment"
            ],
            sentiment_score=validated[
                "sentiment_score"
            ],
            topics=validated[
                "topics"
            ],
            features=validated[
                "features"
            ],
            complaints=validated[
                "complaints"
            ],
            requests=validated[
                "requests"
            ],
            confidence=validated[
                "confidence"
            ],
        )

    @staticmethod
    def _build_prompt(
        retrieved_text: str,
    ) -> str:
        return (
            "Analyze only the supplied source "
            "text.\n"
            "Do not use outside knowledge.\n"
            "Do not infer identity information.\n"
            "Return exactly one JSON object and "
            "no additional text.\n"
            "The JSON object must contain exactly "
            "these fields:\n"
            "sentiment: non-empty string\n"
            "sentiment_score: number from -1 to 1\n"
            "topics: array of strings\n"
            "features: array of strings\n"
            "complaints: array of strings\n"
            "requests: array of strings\n"
            "confidence: number from 0 to 1\n"
            "Use empty arrays when the source "
            "does not support a list value.\n"
            "Do not invent unsupported claims.\n"
            "\n"
            "Source text:\n"
            f"{retrieved_text}"
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
                "Model analysis did not "
                "complete successfully."
            )

        answer = response.get(
            "answer"
        )

        if not isinstance(
            answer,
            str,
        ):
            raise TypeError(
                "Model analysis answer must "
                "be a string."
            )

        clean_answer = (
            answer.strip()
        )

        if not clean_answer:
            raise ValueError(
                "Model analysis returned an "
                "empty answer."
            )

        try:
            payload = json.loads(
                clean_answer
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Model analysis must return "
                "valid JSON."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "Model analysis JSON must be "
                "an object."
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
                "Model analysis schema "
                "does not match the required "
                "fields. "
                f"Missing: {missing}. "
                f"Unexpected: {unexpected}."
            )

        sentiment = cls._require_text(
            payload["sentiment"],
            field_name="sentiment",
        )

        sentiment_score = (
            cls._require_number(
                payload[
                    "sentiment_score"
                ],
                field_name=(
                    "sentiment_score"
                ),
                minimum=-1.0,
                maximum=1.0,
            )
        )

        confidence = (
            cls._require_number(
                payload[
                    "confidence"
                ],
                field_name="confidence",
                minimum=0.0,
                maximum=1.0,
            )
        )

        return {
            "sentiment": sentiment,
            "sentiment_score": (
                sentiment_score
            ),
            "topics": cls._require_text_list(
                payload["topics"],
                field_name="topics",
            ),
            "features": (
                cls._require_text_list(
                    payload["features"],
                    field_name="features",
                )
            ),
            "complaints": (
                cls._require_text_list(
                    payload["complaints"],
                    field_name="complaints",
                )
            ),
            "requests": (
                cls._require_text_list(
                    payload["requests"],
                    field_name="requests",
                )
            ),
            "confidence": confidence,
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
    def _require_number(
        value: Any,
        *,
        field_name: str,
        minimum: float,
        maximum: float,
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
                f"{field_name} must be "
                "a number."
            )

        number = float(
            value
        )

        if not (
            minimum
            <= number
            <= maximum
        ):
            raise ValueError(
                f"{field_name} must be "
                f"between {minimum} and "
                f"{maximum}."
            )

        return number

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

        result: list[str] = []

        for item in value:
            result.append(
                cls._require_text(
                    item,
                    field_name=(
                        f"{field_name} item"
                    ),
                )
            )

        return result
