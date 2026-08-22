from uuid import uuid4

import pytest

from engine.market_intelligence.models import (
    MarketTrend,
    TopicAggregate,
)
from engine.market_intelligence.trend_validation import (
    MarketTrendPolicy,
    MarketTrendValidator,
    TrendQualification,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_aggregate(
    *,
    mention_count: int = 2,
    source_count: int = 2,
    average_confidence: float = 0.8,
    average_sentiment: float = 0.25,
    window_start: str | None = None,
    window_end: str | None = None,
) -> TopicAggregate:
    source_names = [
        runtime_value(
            "source"
        )
        for _ in range(
            source_count
        )
    ]

    return TopicAggregate(
        topic=runtime_value(
            "topic"
        ),
        mention_count=mention_count,
        average_sentiment=(
            average_sentiment
        ),
        average_confidence=(
            average_confidence
        ),
        source_names=source_names,
        window_start=window_start,
        window_end=window_end,
    )


def test_default_policy_values():
    policy = MarketTrendPolicy()

    assert policy.minimum_mentions == 2
    assert policy.minimum_sources == 2
    assert policy.minimum_confidence == 0.6


def test_invalid_minimum_mentions_is_rejected():
    with pytest.raises(
        ValueError
    ):
        MarketTrendPolicy(
            minimum_mentions=0
        )


def test_invalid_minimum_sources_is_rejected():
    with pytest.raises(
        ValueError
    ):
        MarketTrendPolicy(
            minimum_sources=0
        )


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        1.01,
    ],
)
def test_invalid_minimum_confidence_is_rejected(
    value: float,
):
    with pytest.raises(
        ValueError
    ):
        MarketTrendPolicy(
            minimum_confidence=value
        )


def test_qualified_aggregate_passes():
    validator = (
        MarketTrendValidator()
    )

    result = validator.evaluate(
        create_aggregate()
    )

    assert isinstance(
        result,
        TrendQualification,
    )

    assert result.qualified is True
    assert result.reasons == ()


def test_insufficient_mentions_is_rejected():
    validator = (
        MarketTrendValidator()
    )

    result = validator.evaluate(
        create_aggregate(
            mention_count=1
        )
    )

    assert result.qualified is False

    assert (
        "insufficient_mentions"
        in result.reasons
    )


def test_insufficient_sources_is_rejected():
    validator = (
        MarketTrendValidator()
    )

    result = validator.evaluate(
        create_aggregate(
            source_count=1
        )
    )

    assert result.qualified is False

    assert (
        "insufficient_sources"
        in result.reasons
    )


def test_insufficient_confidence_is_rejected():
    validator = (
        MarketTrendValidator()
    )

    result = validator.evaluate(
        create_aggregate(
            average_confidence=0.59
        )
    )

    assert result.qualified is False

    assert (
        "insufficient_confidence"
        in result.reasons
    )


def test_multiple_rejection_reasons_are_returned():
    validator = (
        MarketTrendValidator()
    )

    result = validator.evaluate(
        create_aggregate(
            mention_count=1,
            source_count=1,
            average_confidence=0.2,
        )
    )

    assert result.qualified is False

    assert result.reasons == (
        "insufficient_mentions",
        "insufficient_sources",
        "insufficient_confidence",
    )


def test_custom_policy_is_used():
    validator = (
        MarketTrendValidator(
            policy=MarketTrendPolicy(
                minimum_mentions=3,
                minimum_sources=1,
                minimum_confidence=0.4,
            )
        )
    )

    result = validator.evaluate(
        create_aggregate(
            mention_count=2,
            source_count=1,
            average_confidence=0.9,
        )
    )

    assert result.qualified is False

    assert result.reasons == (
        "insufficient_mentions",
    )


def test_create_trend_from_qualified_aggregate():
    aggregate = create_aggregate(
        mention_count=4,
        source_count=3,
        average_confidence=0.85,
        average_sentiment=-0.25,
    )

    trend = (
        MarketTrendValidator()
        .create_trend(
            aggregate
        )
    )

    assert isinstance(
        trend,
        MarketTrend,
    )

    assert (
        trend.topic
        == aggregate.topic.lower()
    )

    assert (
        trend.mention_count
        == aggregate.mention_count
    )

    assert (
        trend.sentiment_score
        == aggregate.average_sentiment
    )

    assert (
        trend.confidence
        == aggregate.average_confidence
    )

    assert (
        trend.source_count
        == aggregate.source_count
    )


def test_create_trend_preserves_window():
    window_start = runtime_value(
        "window-start"
    )

    window_end = runtime_value(
        "window-end"
    )

    aggregate = create_aggregate(
        window_start=window_start,
        window_end=window_end,
    )

    trend = (
        MarketTrendValidator()
        .create_trend(
            aggregate
        )
    )

    assert (
        trend.window_start
        == window_start
    )

    assert (
        trend.window_end
        == window_end
    )


def test_create_trend_rejects_unqualified_aggregate():
    validator = (
        MarketTrendValidator()
    )

    with pytest.raises(
        ValueError
    ):
        validator.create_trend(
            create_aggregate(
                mention_count=1
            )
        )


def test_batch_qualification_returns_only_valid_trends():
    qualified = create_aggregate(
        mention_count=3,
        source_count=2,
        average_confidence=0.9,
    )

    rejected = create_aggregate(
        mention_count=1,
        source_count=1,
        average_confidence=0.2,
    )

    trends = (
        MarketTrendValidator()
        .qualify(
            [
                qualified,
                rejected,
            ]
        )
    )

    assert len(trends) == 1

    assert (
        trends[0].topic
        == qualified.topic.lower()
    )


def test_non_aggregate_input_is_rejected():
    with pytest.raises(
        TypeError
    ):
        MarketTrendValidator().evaluate(
            {
                "mention_count": 3
            }
        )
