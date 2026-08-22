from __future__ import annotations

from dataclasses import dataclass

from engine.market_intelligence.models import (
    MarketTrend,
    TopicAggregate,
)


@dataclass(frozen=True)
class MarketTrendPolicy:
    minimum_mentions: int = 2
    minimum_sources: int = 2
    minimum_confidence: float = 0.6

    def __post_init__(
        self,
    ) -> None:
        if self.minimum_mentions < 1:
            raise ValueError(
                "minimum_mentions must be "
                "at least 1."
            )

        if self.minimum_sources < 1:
            raise ValueError(
                "minimum_sources must be "
                "at least 1."
            )

        if not (
            0.0
            <= self.minimum_confidence
            <= 1.0
        ):
            raise ValueError(
                "minimum_confidence must be "
                "between 0 and 1."
            )


@dataclass(frozen=True)
class TrendQualification:
    qualified: bool
    reasons: tuple[str, ...]


class MarketTrendValidator:
    def __init__(
        self,
        *,
        policy: MarketTrendPolicy | None = None,
    ) -> None:
        self.policy = (
            policy
            if policy is not None
            else MarketTrendPolicy()
        )

    def evaluate(
        self,
        aggregate: TopicAggregate,
    ) -> TrendQualification:
        if not isinstance(
            aggregate,
            TopicAggregate,
        ):
            raise TypeError(
                "Trend validation requires "
                "a TopicAggregate."
            )

        reasons: list[str] = []

        if (
            aggregate.mention_count
            < self.policy.minimum_mentions
        ):
            reasons.append(
                "insufficient_mentions"
            )

        if (
            aggregate.source_count
            < self.policy.minimum_sources
        ):
            reasons.append(
                "insufficient_sources"
            )

        if (
            aggregate.average_confidence
            < self.policy.minimum_confidence
        ):
            reasons.append(
                "insufficient_confidence"
            )

        return TrendQualification(
            qualified=not reasons,
            reasons=tuple(
                reasons
            ),
        )

    def create_trend(
        self,
        aggregate: TopicAggregate,
    ) -> MarketTrend:
        qualification = self.evaluate(
            aggregate
        )

        if not qualification.qualified:
            raise ValueError(
                "Topic aggregate does not "
                "qualify as a market trend: "
                f"{qualification.reasons}"
            )

        return MarketTrend.create(
            topic=aggregate.topic,
            mention_count=(
                aggregate.mention_count
            ),
            sentiment_score=(
                aggregate.average_sentiment
            ),
            confidence=(
                aggregate.average_confidence
            ),
            source_count=(
                aggregate.source_count
            ),
            window_start=(
                aggregate.window_start
            ),
            window_end=(
                aggregate.window_end
            ),
        )

    def qualify(
        self,
        aggregates: list[
            TopicAggregate
        ],
    ) -> list[MarketTrend]:
        trends: list[
            MarketTrend
        ] = []

        for aggregate in aggregates:
            qualification = (
                self.evaluate(
                    aggregate
                )
            )

            if not qualification.qualified:
                continue

            trends.append(
                self.create_trend(
                    aggregate
                )
            )

        return trends
