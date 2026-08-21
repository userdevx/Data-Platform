from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PublicContentRecord:
    record_id: str
    source_name: str
    source_type: str
    retrieved_text: str

    source_url: str | None = None
    published_at: str | None = None

    collected_at: str = field(
        default_factory=utc_now
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        *,
        source_name: str,
        source_type: str,
        retrieved_text: str,
        source_url: str | None = None,
        published_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PublicContentRecord":
        return cls(
            record_id=str(uuid4()),
            source_name=source_name.strip(),
            source_type=source_type.strip(),
            retrieved_text=retrieved_text,
            source_url=source_url,
            published_at=published_at,
            metadata=metadata or {},
        )

    def to_data_engine_record(
        self,
    ) -> dict[str, Any]:
        return {
            "source": "market_intelligence",
            "category": "public_content",
            "data_type": "source_text",
            "value": {
                "record_id": self.record_id,
                "source_name": self.source_name,
                "source_type": self.source_type,
                "retrieved_text": self.retrieved_text,
                "source_url": self.source_url,
                "published_at": self.published_at,
                "collected_at": self.collected_at,
                "metadata": dict(self.metadata),
            },
            "unit": "record",
        }


@dataclass
class SentimentAnalysis:
    analysis_id: str
    record_id: str
    source_name: str

    sentiment: str
    sentiment_score: float

    topics: list[str]
    features: list[str]
    complaints: list[str]
    requests: list[str]

    confidence: float

    analyzed_at: str = field(
        default_factory=utc_now
    )

    @classmethod
    def create(
        cls,
        *,
        record_id: str,
        source_name: str,
        sentiment: str,
        sentiment_score: float,
        topics: list[str],
        features: list[str],
        complaints: list[str],
        requests: list[str],
        confidence: float,
    ) -> "SentimentAnalysis":
        return cls(
            analysis_id=str(uuid4()),
            record_id=record_id,
            source_name=source_name.strip(),
            sentiment=sentiment.strip().lower(),
            sentiment_score=sentiment_score,
            topics=topics,
            features=features,
            complaints=complaints,
            requests=requests,
            confidence=confidence,
        )

    def to_data_engine_record(
        self,
    ) -> dict[str, Any]:
        return {
            "source": "market_intelligence",
            "category": "content_analysis",
            "data_type": "sentiment_analysis",
            "value": {
                "analysis_id": self.analysis_id,
                "record_id": self.record_id,
                "source_name": self.source_name,
                "sentiment": self.sentiment,
                "sentiment_score": self.sentiment_score,
                "topics": list(self.topics),
                "features": list(self.features),
                "complaints": list(self.complaints),
                "requests": list(self.requests),
                "confidence": self.confidence,
                "analyzed_at": self.analyzed_at,
            },
            "unit": "analysis",
        }


@dataclass
class TopicAggregate:
    topic: str
    mention_count: int
    average_sentiment: float
    average_confidence: float
    source_names: list[str]

    window_start: str | None = None
    window_end: str | None = None

    @property
    def source_count(
        self,
    ) -> int:
        return len(
            set(self.source_names)
        )


@dataclass
class MarketTrend:
    trend_id: str
    topic: str
    mention_count: int
    sentiment_score: float
    confidence: float
    source_count: int

    window_start: str | None = None
    window_end: str | None = None

    created_at: str = field(
        default_factory=utc_now
    )

    @classmethod
    def create(
        cls,
        *,
        topic: str,
        mention_count: int,
        sentiment_score: float,
        confidence: float,
        source_count: int,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> "MarketTrend":
        return cls(
            trend_id=str(uuid4()),
            topic=topic.strip().lower(),
            mention_count=mention_count,
            sentiment_score=sentiment_score,
            confidence=confidence,
            source_count=source_count,
            window_start=window_start,
            window_end=window_end,
        )

    def to_data_engine_record(
        self,
    ) -> dict[str, Any]:
        return {
            "source": "market_intelligence",
            "category": "market_trend",
            "data_type": "topic_sentiment",
            "value": {
                "trend_id": self.trend_id,
                "topic": self.topic,
                "mention_count": self.mention_count,
                "sentiment_score": self.sentiment_score,
                "confidence": self.confidence,
                "source_count": self.source_count,
                "window_start": self.window_start,
                "window_end": self.window_end,
                "created_at": self.created_at,
            },
            "unit": "analysis",
        }


@dataclass
class ProductRequirement:
    requirement_id: str
    category: str
    description: str
    priority: int

    evidence_topics: list[str] = field(
        default_factory=list
    )

    trend_ids: list[str] = field(
        default_factory=list
    )

    confidence: float = 0.0

    created_at: str = field(
        default_factory=utc_now
    )

    @classmethod
    def create(
        cls,
        *,
        category: str,
        description: str,
        priority: int,
        evidence_topics: list[str],
        trend_ids: list[str],
        confidence: float,
    ) -> "ProductRequirement":
        return cls(
            requirement_id=str(uuid4()),
            category=category.strip(),
            description=description.strip(),
            priority=priority,
            evidence_topics=evidence_topics,
            trend_ids=trend_ids,
            confidence=confidence,
        )

    def to_data_engine_record(
        self,
    ) -> dict[str, Any]:
        return {
            "source": "product_intelligence",
            "category": "application_requirement",
            "data_type": self.category,
            "value": {
                "requirement_id": self.requirement_id,
                "description": self.description,
                "priority": self.priority,
                "evidence_topics": list(
                    self.evidence_topics
                ),
                "trend_ids": list(
                    self.trend_ids
                ),
                "confidence": self.confidence,
                "created_at": self.created_at,
            },
            "unit": "requirement",
        }


@dataclass
class ResearchResult:
    content_count: int
    analysis_count: int
    trends: list[MarketTrend]
    requirements: list[ProductRequirement]
