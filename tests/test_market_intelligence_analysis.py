from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest

from engine.market_intelligence.analysis import (
    MarketIntelligenceAnalyzer,
)
from engine.market_intelligence.models import (
    PublicContentRecord,
    SentimentAnalysis,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_record(
    text: str | None = None,
) -> PublicContentRecord:
    return PublicContentRecord.create(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        retrieved_text=(
            text
            if text is not None
            else runtime_value(
                "evidence"
            )
        ),
    )


def valid_payload() -> dict[str, Any]:
    return {
        "sentiment":
            runtime_value(
                "sentiment"
            ),
        "sentiment_score":
            0.25,
        "topics": [
            runtime_value(
                "topic"
            )
        ],
        "features": [
            runtime_value(
                "feature"
            )
        ],
        "complaints": [
            runtime_value(
                "complaint"
            )
        ],
        "requests": [
            runtime_value(
                "request"
            )
        ],
        "confidence":
            0.75,
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


def test_valid_model_output_creates_analysis():
    payload = valid_payload()

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    record = create_record()

    result = analyzer.analyze(
        record
    )

    assert isinstance(
        result,
        SentimentAnalysis,
    )

    assert (
        result.record_id
        == record.record_id
    )

    assert (
        result.source_name
        == record.source_name
    )

    assert (
        result.sentiment
        == payload["sentiment"]
    )

    assert (
        result.sentiment_score
        == payload[
            "sentiment_score"
        ]
    )

    assert (
        result.confidence
        == payload["confidence"]
    )


def test_runtime_uses_text_input_capability():
    request, calls = (
        successful_model_request(
            valid_payload()
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    analyzer.analyze(
        create_record()
    )

    assert len(calls) == 1

    assert (
        calls[0][
            "required_capability"
        ]
        == "text_input"
    )


def test_prompt_contains_only_runtime_source_text():
    payload = valid_payload()

    request, calls = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    text = runtime_value(
        "source-text"
    )

    analyzer.analyze(
        create_record(
            text
        )
    )

    assert text in (
        calls[0]["question"]
    )

    assert (
        "Return exactly one JSON object"
        in calls[0]["question"]
    )


def test_record_provenance_cannot_be_replaced_by_model():
    payload = valid_payload()

    payload[
        "record_id"
    ] = runtime_value(
        "model-record"
    )

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            create_record()
        )


def test_missing_field_is_rejected():
    payload = valid_payload()

    payload.pop(
        "confidence"
    )

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            create_record()
        )


def test_unexpected_field_is_rejected():
    payload = valid_payload()

    payload[
        runtime_value(
            "unexpected"
        )
    ] = True

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            create_record()
        )


def test_invalid_json_is_rejected():
    def request(
        *,
        question: str,
        required_capability: str,
    ) -> dict[str, Any]:
        return {
            "status": "success",
            "answer": (
                runtime_value(
                    "not-json"
                )
            ),
        }

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            create_record()
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

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        RuntimeError
    ):
        analyzer.analyze(
            create_record()
        )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "sentiment_score",
            -1.01,
        ),
        (
            "sentiment_score",
            1.01,
        ),
        (
            "confidence",
            -0.01,
        ),
        (
            "confidence",
            1.01,
        ),
    ],
)
def test_numeric_ranges_are_enforced(
    field: str,
    value: float,
):
    payload = valid_payload()

    payload[field] = value

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            create_record()
        )


def test_boolean_is_not_accepted_as_number():
    payload = valid_payload()

    payload[
        "confidence"
    ] = True

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        TypeError
    ):
        analyzer.analyze(
            create_record()
        )


def test_signal_fields_must_be_lists():
    payload = valid_payload()

    payload[
        "topics"
    ] = runtime_value(
        "not-list"
    )

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        TypeError
    ):
        analyzer.analyze(
            create_record()
        )


def test_signal_list_items_must_be_non_empty_strings():
    payload = valid_payload()

    payload[
        "requests"
    ] = [
        ""
    ]

    request, _ = (
        successful_model_request(
            payload
        )
    )

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            create_record()
        )


def test_empty_source_text_is_rejected_before_model_call():
    calls = 0

    def request(
        *,
        question: str,
        required_capability: str,
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1

        return {
            "status": "success",
            "answer": json.dumps(
                valid_payload()
            ),
        }

    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=request
        )
    )

    record = create_record(
        "   "
    )

    with pytest.raises(
        ValueError
    ):
        analyzer.analyze(
            record
        )

    assert calls == 0


def test_non_record_input_is_rejected():
    analyzer = (
        MarketIntelligenceAnalyzer(
            model_request=lambda **_: {}
        )
    )

    with pytest.raises(
        TypeError
    ):
        analyzer.analyze(
            {
                "retrieved_text":
                    runtime_value(
                        "text"
                    )
            }
        )
