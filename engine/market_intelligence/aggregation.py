from __future__ import annotations

from dataclasses import dataclass, field

from engine.market_intelligence.models import (
    SentimentAnalysis,
    TopicAggregate,
)


@dataclass
class _TopicAccumulator:
    sentiment_scores: list[float] = field(
        default_factory=list
    )

    confidence_scores: list[float] = field(
        default_factory=list
    )

    source_names: list[str] = field(
        default_factory=list
    )

    normalized_sources: set[str] = field(
        default_factory=set
    )

    def add(
        self,
        analysis: SentimentAnalysis,
    ) -> None:
        self.sentiment_scores.append(
            float(
                analysis.sentiment_score
            )
        )

        self.confidence_scores.append(
            float(
                analysis.confidence
            )
        )

        source_name = (
            analysis.source_name.strip()
        )

        normalized_source = (
            source_name.casefold()
        )

        if (
            normalized_source
            not in self.normalized_sources
        ):
            self.normalized_sources.add(
                normalized_source
            )

            self.source_names.append(
                source_name
            )


class TopicAggregator:
    def aggregate(
        self,
        analyses: list[
            SentimentAnalysis
        ],
    ) -> list[TopicAggregate]:
        accumulators: dict[
            str,
            _TopicAccumulator,
        ] = {}

        for analysis in analyses:
            if not isinstance(
                analysis,
                SentimentAnalysis,
            ):
                raise TypeError(
                    "Topic aggregation requires "
                    "SentimentAnalysis objects."
                )

            topics = self._unique_topics(
                analysis.topics
            )

            for topic in topics:
                accumulator = (
                    accumulators.setdefault(
                        topic,
                        _TopicAccumulator(),
                    )
                )

                accumulator.add(
                    analysis
                )

        aggregates: list[
            TopicAggregate
        ] = []

        for topic in sorted(
            accumulators
        ):
            accumulator = (
                accumulators[topic]
            )

            mention_count = len(
                accumulator.sentiment_scores
            )

            aggregates.append(
                TopicAggregate(
                    topic=topic,
                    mention_count=(
                        mention_count
                    ),
                    average_sentiment=(
                        sum(
                            accumulator
                            .sentiment_scores
                        )
                        / mention_count
                    ),
                    average_confidence=(
                        sum(
                            accumulator
                            .confidence_scores
                        )
                        / mention_count
                    ),
                    source_names=list(
                        accumulator
                        .source_names
                    ),
                )
            )

        return aggregates

    @classmethod
    def _unique_topics(
        cls,
        topics: list[str],
    ) -> tuple[str, ...]:
        unique: list[str] = []
        seen: set[str] = set()

        for topic in topics:
            normalized = (
                cls._normalize_topic(
                    topic
                )
            )

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            unique.append(
                normalized
            )

        return tuple(
            unique
        )

    @staticmethod
    def _normalize_topic(
        topic: str,
    ) -> str:
        if not isinstance(
            topic,
            str,
        ):
            raise TypeError(
                "Topic values must be strings."
            )

        normalized = " ".join(
            topic.split()
        ).casefold()

        if not normalized:
            raise ValueError(
                "Topic values cannot be empty."
            )

        return normalized
