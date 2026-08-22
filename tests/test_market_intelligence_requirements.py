from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest

from engine.market_intelligence.models import (
    MarketTrend,
    ProductRequirement,
)
from engine.market_intelligence.requirements import (
    ProductRequirementGenerator,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_trend(
    *,
    topic: str | None = None,
    confidence: float = 0.8,
) -> MarketTrend:
    return MarketTrend.create(
        topic=(
            topic
            if topic is not None
            else runtime_value(
                "topic"
            )
        ),
        mention_count=3,
        sentiment_score=0.25,
        confidence=confidence,
        source_count=2,
    )


def valid_payload() -> dict[str, Any]:
    return {
        "category":
            runtime_value(
                "category"
            ),
        "description":
            runtime_value(
                "description"
            ),
        "priority":
            3,
    }


def successful_model_request(
    payload: dict[str, Any],
):
    calls: list[
        dict[str, Any]
    ] = []

    def request(
        *,
        question: str,
        required_capability: str,
    ) -> dict[str, Any]:
        calls.append(
            {
                "question": question,
                "required_capability": (
                    required_capability
                ),
            }
        )

        return {
            "status": "success",
            "answer": json.dumps(
                payload
            ),
        }

    return request, calls


def test_valid_proposal_creates_requirement():
    payload = valid_payload()

    request, _ = (
        successful_model_request(
            payload
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    trend = create_trend()

    result = generator.generate(
        [trend]
    )

    assert isinstance(
        result,
        ProductRequirement,
    )

    assert (
        result.category
        == payload["category"]
    )

    assert (
        result.description
        == payload["description"]
    )

    assert (
        result.priority
        == payload["priority"]
    )


def test_runtime_uses_text_input_capability():
    request, calls = (
        successful_model_request(
            valid_payload()
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    generator.generate(
        [
            create_trend()
        ]
    )

    assert len(calls) == 1

    assert (
        calls[0][
            "required_capability"
        ]
        == "text_input"
    )


def test_trend_provenance_is_added_by_platform():
    request, _ = (
        successful_model_request(
            valid_payload()
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    first = create_trend()
    second = create_trend()

    result = generator.generate(
        [
            first,
            second,
        ]
    )

    assert result.trend_ids == [
        first.trend_id,
        second.trend_id,
    ]

    assert result.evidence_topics == [
        first.topic,
        second.topic,
    ]


def test_requirement_confidence_is_average_of_trends():
    request, _ = (
        successful_model_request(
            valid_payload()
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    first = create_trend(
        confidence=0.6
    )

    second = create_trend(
        confidence=0.8
    )

    result = generator.generate(
        [
            first,
            second,
        ]
    )

    assert result.confidence == (
        pytest.approx(
            0.7
        )
    )


def test_duplicate_topics_are_removed():
    topic = runtime_value(
        "topic"
    )

    first = create_trend(
        topic=topic
    )

    second = create_trend(
        topic=topic.upper()
    )

    request, _ = (
        successful_model_request(
            valid_payload()
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    result = generator.generate(
        [
            first,
            second,
        ]
    )

    assert result.evidence_topics == [
        first.topic
    ]


def test_duplicate_trend_ids_are_removed():
    first = create_trend()
    second = create_trend()

    second.trend_id = (
        first.trend_id
    )

    request, _ = (
        successful_model_request(
            valid_payload()
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    result = generator.generate(
        [
            first,
            second,
        ]
    )

    assert result.trend_ids == [
        first.trend_id
    ]


def test_model_cannot_supply_provenance():
    payload = valid_payload()

    payload[
        "trend_ids"
    ] = [
        runtime_value(
            "model-trend"
        )
    ]

    request, _ = (
        successful_model_request(
            payload
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        generator.generate(
            [
                create_trend()
            ]
        )


def test_missing_field_is_rejected():
    payload = valid_payload()

    payload.pop(
        "description"
    )

    request, _ = (
        successful_model_request(
            payload
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        generator.generate(
            [
                create_trend()
            ]
        )


def test_invalid_json_is_rejected():
    def request(
        *,
        question: str,
        required_capability: str,
    ) -> dict[str, Any]:
        return {
            "status": "success",
            "answer": runtime_value(
                "not-json"
            ),
        }

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        generator.generate(
            [
                create_trend()
            ]
        )


def test_non_success_status_is_rejected():
    def request(
        *,
        question: str,
        required_capability: str,
    ) -> dict[str, Any]:
        return {
            "status": "error",
            "answer": "",
        }

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    with pytest.raises(
        RuntimeError
    ):
        generator.generate(
            [
                create_trend()
            ]
        )


@pytest.mark.parametrize(
    "priority",
    [
        0,
        6,
    ],
)
def test_priority_range_is_enforced(
    priority: int,
):
    payload = valid_payload()

    payload[
        "priority"
    ] = priority

    request, _ = (
        successful_model_request(
            payload
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        generator.generate(
            [
                create_trend()
            ]
        )


def test_boolean_priority_is_rejected():
    payload = valid_payload()

    payload[
        "priority"
    ] = True

    request, _ = (
        successful_model_request(
            payload
        )
    )

    generator = (
        ProductRequirementGenerator(
            model_request=request
        )
    )

    with pytest.raises(
        TypeError
    ):
        generator.generate(
            [
                create_trend()
            ]
        )


def test_empty_trend_list_is_rejected():
    generator = (
        ProductRequirementGenerator(
            model_request=lambda **_: {}
        )
    )

    with pytest.raises(
        ValueError
    ):
        generator.generate([])


def test_non_list_trends_are_rejected():
    generator = (
        ProductRequirementGenerator(
            model_request=lambda **_: {}
        )
    )

    with pytest.raises(
        TypeError
    ):
        generator.generate(
            (
                create_trend(),
            )
        )


def test_non_trend_input_is_rejected():
    generator = (
        ProductRequirementGenerator(
            model_request=lambda **_: {}
        )
    )

    with pytest.raises(
        TypeError
    ):
        generator.generate(
            [
                {
                    "topic":
                        runtime_value(
                            "topic"
                        )
                }
            ]
        )
