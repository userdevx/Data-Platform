from __future__ import annotations

from typing import Any

import pytest

from engine.market_intelligence.data_engine_writer import (
    MarketIntelligenceDataEngineWriter,
)
from engine.market_intelligence.models import (
    MarketTrend,
    ProductRequirement,
    PublicContentRecord,
    SentimentAnalysis,
)
from engine.query import QueryService


class MemoryBackend:
    def __init__(self) -> None:
        self.records: list[
            dict[str, Any]
        ] = []

    def get_all_records(
        self,
    ) -> list[dict[str, Any]]:
        return [
            dict(record)
            for record in self.records
        ]

    def insert_record(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        record_id = record["id"]

        if any(
            existing["id"]
            == record_id
            for existing in self.records
        ):
            raise ValueError(
                "Duplicate record id."
            )

        stored = dict(
            record
        )

        self.records.append(
            stored
        )

        return stored

    def get_record_by_id(
        self,
        record_id: int,
    ) -> dict[str, Any]:
        for record in self.records:
            if (
                record["id"]
                == record_id
            ):
                return dict(
                    record
                )

        raise KeyError(
            record_id
        )

    def update_record(
        self,
        record_id: int,
        updated_data: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def delete_record(
        self,
        record_id: int,
    ) -> dict[str, Any]:
        raise NotImplementedError


def create_writer():
    backend = MemoryBackend()

    service = QueryService(
        backend
    )

    writer = (
        MarketIntelligenceDataEngineWriter(
            query_service=service
        )
    )

    return (
        backend,
        writer,
    )


def test_public_content_is_written_as_data_record():
    backend, writer = create_writer()

    entity = PublicContentRecord.create(
        source_name="runtime_source",
        source_type="public_information",
        retrieved_text="runtime text",
    )

    stored = writer.write(
        entity
    )

    assert stored["id"] == 1
    assert (
        stored["source"]
        == "market_intelligence"
    )
    assert (
        stored["category"]
        == "public_content"
    )
    assert (
        stored["data_type"]
        == "source_text"
    )
    assert (
        stored["value"]["record_id"]
        == entity.record_id
    )

    assert len(
        backend.records
    ) == 1


def test_sentiment_analysis_is_written():
    _, writer = create_writer()

    entity = SentimentAnalysis.create(
        record_id="runtime-record",
        source_name="runtime_source",
        sentiment="positive",
        sentiment_score=0.5,
        topics=[
            "runtime_topic",
        ],
        features=[],
        complaints=[],
        requests=[],
        confidence=0.8,
    )

    stored = writer.write(
        entity
    )

    assert (
        stored["data_type"]
        == "sentiment_analysis"
    )

    assert (
        stored["value"][
            "analysis_id"
        ]
        == entity.analysis_id
    )


def test_market_trend_is_written():
    _, writer = create_writer()

    entity = MarketTrend.create(
        topic="runtime_topic",
        mention_count=10,
        sentiment_score=0.2,
        confidence=0.75,
        source_count=2,
    )

    stored = writer.write(
        entity
    )

    assert (
        stored["category"]
        == "market_trend"
    )

    assert (
        stored["value"]["trend_id"]
        == entity.trend_id
    )


def test_product_requirement_is_written():
    _, writer = create_writer()

    entity = ProductRequirement.create(
        category="runtime_requirement",
        description="runtime requirement",
        priority=1,
        evidence_topics=[
            "runtime_topic",
        ],
        trend_ids=[
            "runtime-trend",
        ],
        confidence=0.85,
    )

    stored = writer.write(
        entity
    )

    assert (
        stored["category"]
        == "application_requirement"
    )

    assert (
        stored["data_type"]
        == "runtime_requirement"
    )

    assert (
        stored["value"][
            "requirement_id"
        ]
        == entity.requirement_id
    )


def test_record_ids_increment():
    _, writer = create_writer()

    first = PublicContentRecord.create(
        source_name="runtime_source",
        source_type="public_information",
        retrieved_text="first",
    )

    second = PublicContentRecord.create(
        source_name="runtime_source",
        source_type="public_information",
        retrieved_text="second",
    )

    first_record = writer.write(
        first
    )

    second_record = writer.write(
        second
    )

    assert first_record["id"] == 1
    assert second_record["id"] == 2


def test_existing_ids_are_respected():
    backend, writer = create_writer()

    backend.records.append(
        {
            "id": 41,
            "source": "runtime_source",
            "category": "runtime_category",
            "data_type": "runtime_data",
            "value": 1,
            "unit": "record",
            "created_at": "runtime-created",
            "updated_at": "runtime-updated",
        }
    )

    entity = PublicContentRecord.create(
        source_name="runtime_source",
        source_type="public_information",
        retrieved_text="runtime text",
    )

    stored = writer.write(
        entity
    )

    assert stored["id"] == 42


def test_created_and_updated_timestamps_are_generated():
    _, writer = create_writer()

    entity = PublicContentRecord.create(
        source_name="runtime_source",
        source_type="public_information",
        retrieved_text="runtime text",
    )

    stored = writer.write(
        entity
    )

    assert stored["created_at"]
    assert stored["updated_at"]

    assert (
        stored["created_at"]
        == stored["updated_at"]
    )


def test_missing_payload_field_is_rejected():
    _, writer = create_writer()

    with pytest.raises(
        ValueError
    ):
        writer.write_payload(
            {
                "source":
                    "runtime_source",
                "category":
                    "runtime_category",
                "data_type":
                    "runtime_data",
                "value":
                    1,
            }
        )


def test_none_value_is_rejected():
    _, writer = create_writer()

    with pytest.raises(
        ValueError
    ):
        writer.write_payload(
            {
                "source":
                    "runtime_source",
                "category":
                    "runtime_category",
                "data_type":
                    "runtime_data",
                "value":
                    None,
                "unit":
                    "record",
            }
        )
