from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from engine.market_intelligence.ingestion import (
    MarketIntelligenceIngestionPipeline,
)
from engine.market_intelligence.models import (
    PublicContentRecord,
)
from engine.market_intelligence.sources.base import (
    PublicSource,
)
from engine.market_intelligence.sources.registry import (
    PublicSourceRegistry,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


class RuntimeSource(
    PublicSource
):
    def __init__(
        self,
        *,
        source_name: str,
        source_type: str,
        records: list[
            PublicContentRecord
        ],
    ) -> None:
        self._source_name = (
            source_name
        )
        self._source_type = (
            source_type
        )
        self.records = records

        self.received_queries: list[
            str
        ] = []

        self.received_limits: list[
            int
        ] = []

    @property
    def source_name(
        self,
    ) -> str:
        return self._source_name

    @property
    def source_type(
        self,
    ) -> str:
        return self._source_type

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[
        PublicContentRecord
    ]:
        self.received_queries.append(
            query
        )

        self.received_limits.append(
            limit
        )

        return list(
            self.records
        )


class RecordingWriter:
    def __init__(
        self,
    ) -> None:
        self.entities: list[
            PublicContentRecord
        ] = []

    def write(
        self,
        entity: PublicContentRecord,
    ) -> dict[str, Any]:
        self.entities.append(
            entity
        )

        return {
            "id": len(
                self.entities
            ),
            "value": (
                entity
                .to_data_engine_record()[
                    "value"
                ]
            ),
        }


def create_record(
    *,
    text: str,
    metadata: dict[
        str,
        Any
    ] | None = None,
) -> PublicContentRecord:
    return PublicContentRecord.create(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        retrieved_text=text,
        metadata=metadata,
    )


def create_pipeline(
    *sources: RuntimeSource,
) -> tuple[
    MarketIntelligenceIngestionPipeline,
    RecordingWriter,
]:
    registry = (
        PublicSourceRegistry()
    )

    for source in sources:
        registry.register(
            source
        )

    writer = RecordingWriter()

    pipeline = (
        MarketIntelligenceIngestionPipeline(
            registry=registry,
            writer=writer,
        )
    )

    return (
        pipeline,
        writer,
    )


def test_ingests_all_registered_sources():
    first = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=runtime_value(
                    "first"
                )
            )
        ],
    )

    second = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=runtime_value(
                    "second"
                )
            )
        ],
    )

    pipeline, writer = (
        create_pipeline(
            first,
            second,
        )
    )

    result = pipeline.ingest(
        runtime_value(
            "query"
        )
    )

    assert result.collected_count == 2
    assert result.unique_count == 2
    assert result.duplicate_count == 0
    assert len(writer.entities) == 2


def test_selected_source_is_used():
    first = RuntimeSource(
        source_name=runtime_value(
            "first"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=runtime_value(
                    "first-text"
                )
            )
        ],
    )

    second = RuntimeSource(
        source_name=runtime_value(
            "second"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=runtime_value(
                    "second-text"
                )
            )
        ],
    )

    pipeline, writer = (
        create_pipeline(
            first,
            second,
        )
    )

    pipeline.ingest(
        runtime_value(
            "query"
        ),
        source_names=[
            second.source_name
        ],
    )

    assert not first.received_queries
    assert len(second.received_queries) == 1
    assert len(writer.entities) == 1


def test_query_is_trimmed_before_search():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    value = runtime_value(
        "query"
    )

    pipeline.ingest(
        f"  {value}  "
    )

    assert (
        source.received_queries
        == [value]
    )


def test_limit_is_forwarded_to_source():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    pipeline.ingest(
        runtime_value(
            "query"
        ),
        limit=7,
    )

    assert (
        source.received_limits
        == [7]
    )


def test_metadata_is_sanitized_before_write():
    record = create_record(
        text=runtime_value(
            "text"
        ),
        metadata={
            "username":
                runtime_value(
                    "identity"
                ),
            "language":
                runtime_value(
                    "language"
                ),
        },
    )

    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            record
        ],
    )

    pipeline, writer = (
        create_pipeline(
            source
        )
    )

    pipeline.ingest(
        runtime_value(
            "query"
        )
    )

    assert "username" not in (
        writer.entities[0]
        .metadata
    )

    assert "language" in (
        writer.entities[0]
        .metadata
    )


def test_text_is_normalized_before_write():
    value = runtime_value(
        "text"
    )

    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=(
                    f"  {value}\n\n"
                )
            )
        ],
    )

    pipeline, writer = (
        create_pipeline(
            source
        )
    )

    pipeline.ingest(
        runtime_value(
            "query"
        )
    )

    assert (
        writer.entities[0]
        .retrieved_text
        == value
    )


def test_cross_source_duplicates_are_written_once():
    value = runtime_value(
        "shared"
    )

    first = RuntimeSource(
        source_name=runtime_value(
            "first"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=value
            )
        ],
    )

    second = RuntimeSource(
        source_name=runtime_value(
            "second"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[
            create_record(
                text=(
                    f"  {value.upper()}  "
                )
            )
        ],
    )

    pipeline, writer = (
        create_pipeline(
            first,
            second,
        )
    )

    result = pipeline.ingest(
        runtime_value(
            "query"
        )
    )

    assert result.collected_count == 2
    assert result.unique_count == 1
    assert result.duplicate_count == 1
    assert len(writer.entities) == 1


def test_duplicate_source_names_are_resolved_once():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    pipeline.ingest(
        runtime_value(
            "query"
        ),
        source_names=[
            source.source_name,
            source.source_name.upper(),
        ],
    )

    assert len(
        source.received_queries
    ) == 1


def test_empty_query_is_rejected():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    with pytest.raises(
        ValueError
    ):
        pipeline.ingest(
            "   "
        )


def test_non_string_query_is_rejected():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    with pytest.raises(
        TypeError
    ):
        pipeline.ingest(
            1
        )


def test_invalid_limit_is_rejected():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    with pytest.raises(
        ValueError
    ):
        pipeline.ingest(
            runtime_value(
                "query"
            ),
            limit=0,
        )

    with pytest.raises(
        TypeError
    ):
        pipeline.ingest(
            runtime_value(
                "query"
            ),
            limit=True,
        )


def test_non_public_content_record_is_rejected():
    source = RuntimeSource(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        records=[],
    )

    source.records = [
        {
            "value":
                runtime_value(
                    "invalid"
                )
        }
    ]

    pipeline, _ = (
        create_pipeline(
            source
        )
    )

    with pytest.raises(
        TypeError
    ):
        pipeline.ingest(
            runtime_value(
                "query"
            )
        )
