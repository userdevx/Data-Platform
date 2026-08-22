from uuid import uuid4

import pytest

from engine.market_intelligence.aggregation import (
    TopicAggregator,
)
from engine.market_intelligence.models import (
    SentimentAnalysis,
    TopicAggregate,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_analysis(
    *,
    source_name: str,
    topics: list[str],
    sentiment_score: float,
    confidence: float,
) -> SentimentAnalysis:
    return SentimentAnalysis.create(
        record_id=runtime_value(
            "record"
        ),
        source_name=source_name,
        sentiment=runtime_value(
            "sentiment"
        ),
        sentiment_score=(
            sentiment_score
        ),
        topics=topics,
        features=[],
        complaints=[],
        requests=[],
        confidence=confidence,
    )


def test_single_topic_creates_aggregate():
    topic = runtime_value(
        "topic"
    )

    source = runtime_value(
        "source"
    )

    analysis = create_analysis(
        source_name=source,
        topics=[topic],
        sentiment_score=0.4,
        confidence=0.8,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [analysis]
        )
    )

    assert len(result) == 1
    assert isinstance(
        result[0],
        TopicAggregate,
    )

    assert (
        result[0].topic
        == topic.casefold()
    )

    assert (
        result[0].mention_count
        == 1
    )

    assert (
        result[0].average_sentiment
        == 0.4
    )

    assert (
        result[0].average_confidence
        == 0.8
    )

    assert result[0].source_count == 1


def test_repeated_topic_is_aggregated():
    topic = runtime_value(
        "topic"
    )

    first = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[topic],
        sentiment_score=0.2,
        confidence=0.6,
    )

    second = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[topic],
        sentiment_score=0.6,
        confidence=0.8,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [
                first,
                second,
            ]
        )
    )

    assert len(result) == 1

    aggregate = result[0]

    assert (
        aggregate.mention_count
        == 2
    )

    assert (
        aggregate.average_sentiment
        == pytest.approx(
            0.4
        )
    )

    assert (
        aggregate.average_confidence
        == pytest.approx(
            0.7
        )
    )

    assert aggregate.source_count == 2


def test_repeated_topic_inside_one_analysis_counts_once():
    topic = runtime_value(
        "topic"
    )

    analysis = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[
            topic,
            topic.upper(),
            f"  {topic}  ",
        ],
        sentiment_score=0.5,
        confidence=0.9,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [analysis]
        )
    )

    assert len(result) == 1
    assert (
        result[0].mention_count
        == 1
    )


def test_topic_whitespace_is_normalized():
    first = runtime_value(
        "first"
    )

    second = runtime_value(
        "second"
    )

    analysis = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[
            f"  {first}\n\t{second}  "
        ],
        sentiment_score=0.0,
        confidence=0.5,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [analysis]
        )
    )

    assert (
        result[0].topic
        == (
            f"{first} {second}"
            .casefold()
        )
    )


def test_source_names_are_case_insensitive_for_source_count():
    topic = runtime_value(
        "topic"
    )

    source = runtime_value(
        "source"
    )

    first = create_analysis(
        source_name=source,
        topics=[topic],
        sentiment_score=0.1,
        confidence=0.7,
    )

    second = create_analysis(
        source_name=source.upper(),
        topics=[topic],
        sentiment_score=0.3,
        confidence=0.9,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [
                first,
                second,
            ]
        )
    )

    aggregate = result[0]

    assert (
        aggregate.mention_count
        == 2
    )

    assert aggregate.source_count == 1


def test_distinct_sources_are_preserved():
    topic = runtime_value(
        "topic"
    )

    first_source = runtime_value(
        "first-source"
    )

    second_source = runtime_value(
        "second-source"
    )

    first = create_analysis(
        source_name=first_source,
        topics=[topic],
        sentiment_score=0.0,
        confidence=0.5,
    )

    second = create_analysis(
        source_name=second_source,
        topics=[topic],
        sentiment_score=0.0,
        confidence=0.5,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [
                first,
                second,
            ]
        )
    )

    assert result[0].source_names == [
        first_source,
        second_source,
    ]

    assert result[0].source_count == 2


def test_multiple_topics_create_multiple_aggregates():
    first_topic = runtime_value(
        "first-topic"
    )

    second_topic = runtime_value(
        "second-topic"
    )

    analysis = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[
            second_topic,
            first_topic,
        ],
        sentiment_score=0.0,
        confidence=0.5,
    )

    result = (
        TopicAggregator()
        .aggregate(
            [analysis]
        )
    )

    assert [
        item.topic
        for item in result
    ] == sorted(
        [
            first_topic.casefold(),
            second_topic.casefold(),
        ]
    )


def test_empty_analysis_list_returns_empty_list():
    assert (
        TopicAggregator()
        .aggregate([])
        == []
    )


def test_non_analysis_input_is_rejected():
    with pytest.raises(
        TypeError
    ):
        TopicAggregator().aggregate(
            [
                {
                    "topics": []
                }
            ]
        )


def test_non_string_topic_is_rejected():
    analysis = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[],
        sentiment_score=0.0,
        confidence=0.5,
    )

    analysis.topics = [
        1
    ]

    with pytest.raises(
        TypeError
    ):
        TopicAggregator().aggregate(
            [analysis]
        )


def test_empty_topic_is_rejected():
    analysis = create_analysis(
        source_name=runtime_value(
            "source"
        ),
        topics=[
            "   "
        ],
        sentiment_score=0.0,
        confidence=0.5,
    )

    with pytest.raises(
        ValueError
    ):
        TopicAggregator().aggregate(
            [analysis]
        )
