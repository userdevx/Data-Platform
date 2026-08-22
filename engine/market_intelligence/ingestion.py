from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.market_intelligence.data_engine_writer import (
    MarketIntelligenceDataEngineWriter,
)
from engine.market_intelligence.deduplication import (
    deduplicate_public_content,
)
from engine.market_intelligence.models import (
    PublicContentRecord,
)
from engine.market_intelligence.normalization import (
    normalize_public_content,
)
from engine.market_intelligence.privacy import (
    MetadataSanitizer,
)
from engine.market_intelligence.sources.base import (
    PublicSource,
)
from engine.market_intelligence.sources.registry import (
    PublicSourceRegistry,
)


@dataclass(frozen=True)
class IngestionResult:
    collected_count: int
    unique_count: int
    duplicate_count: int
    stored_records: tuple[
        dict[str, Any],
        ...,
    ]


class MarketIntelligenceIngestionPipeline:
    def __init__(
        self,
        *,
        registry: PublicSourceRegistry,
        writer: MarketIntelligenceDataEngineWriter,
        metadata_sanitizer: MetadataSanitizer | None = None,
    ) -> None:
        self.registry = registry
        self.writer = writer

        self.metadata_sanitizer = (
            metadata_sanitizer
            if metadata_sanitizer is not None
            else MetadataSanitizer()
        )

    def ingest(
        self,
        query: str,
        *,
        source_names: list[str] | None = None,
        limit: int = 50,
    ) -> IngestionResult:
        normalized_query = (
            self._normalize_query(
                query
            )
        )

        normalized_limit = (
            self._validate_limit(
                limit
            )
        )

        sources = self._resolve_sources(
            source_names
        )

        collected: list[
            PublicContentRecord
        ] = []

        for source in sources:
            records = source.search(
                normalized_query,
                limit=normalized_limit,
            )

            collected.extend(
                self._prepare_records(
                    records
                )
            )

        unique_records = (
            deduplicate_public_content(
                collected
            )
        )

        stored_records = tuple(
            self.writer.write(
                record
            )
            for record in unique_records
        )

        collected_count = len(
            collected
        )

        unique_count = len(
            unique_records
        )

        return IngestionResult(
            collected_count=collected_count,
            unique_count=unique_count,
            duplicate_count=(
                collected_count
                - unique_count
            ),
            stored_records=stored_records,
        )

    def _resolve_sources(
        self,
        source_names: list[str] | None,
    ) -> tuple[PublicSource, ...]:
        if source_names is None:
            return self.registry.all()

        resolved: list[
            PublicSource
        ] = []

        seen_names: set[str] = set()

        for source_name in source_names:
            normalized_name = (
                source_name
                .strip()
                .casefold()
            )

            if not normalized_name:
                raise ValueError(
                    "Source name cannot be empty."
                )

            if normalized_name in seen_names:
                continue

            seen_names.add(
                normalized_name
            )

            resolved.append(
                self.registry.get(
                    source_name
                )
            )

        return tuple(
            resolved
        )

    def _prepare_records(
        self,
        records: list[PublicContentRecord],
    ) -> list[PublicContentRecord]:
        prepared: list[
            PublicContentRecord
        ] = []

        for record in records:
            if not isinstance(
                record,
                PublicContentRecord,
            ):
                raise TypeError(
                    "Public sources must return "
                    "PublicContentRecord objects."
                )

            record.metadata = (
                self.metadata_sanitizer
                .sanitize(
                    record.metadata
                )
            )

            normalize_public_content(
                record
            )

            prepared.append(
                record
            )

        return prepared

    @staticmethod
    def _normalize_query(
        query: str,
    ) -> str:
        if not isinstance(
            query,
            str,
        ):
            raise TypeError(
                "Research query must be a string."
            )

        normalized = query.strip()

        if not normalized:
            raise ValueError(
                "Research query cannot be empty."
            )

        return normalized

    @staticmethod
    def _validate_limit(
        limit: int,
    ) -> int:
        if (
            not isinstance(
                limit,
                int,
            )
            or isinstance(
                limit,
                bool,
            )
        ):
            raise TypeError(
                "Source result limit must be an integer."
            )

        if limit < 1:
            raise ValueError(
                "Source result limit must be greater than zero."
            )

        return limit
