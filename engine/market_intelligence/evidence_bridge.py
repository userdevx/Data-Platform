from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from engine.backend import get_backend
from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.evidence.models import (
    NormalizedInformation,
    RawInformation,
)
from engine.evidence.serialization import (
    serialize_entity,
)
from engine.query import QueryService


SOURCE_TEXT_DATA_TYPE = "source_text"

STRUCTURED_KNOWLEDGE_DATA_TYPE = (
    "structured_knowledge"
)

RAW_INFORMATION_DATA_TYPE = (
    "raw_information"
)

NORMALIZED_INFORMATION_DATA_TYPE = (
    "normalized_information"
)


@dataclass(
    frozen=True,
    kw_only=True,
)
class EvidenceBridgeResult:
    source_record_id: int
    raw_information: RawInformation
    normalized_information: NormalizedInformation
    raw_record: dict[str, Any]
    normalized_record: dict[str, Any]


@dataclass(
    frozen=True,
    kw_only=True,
)
class EvidencePersistenceResult:
    source_record_id: int

    raw_data_engine_record: dict[str, Any]

    normalized_data_engine_record: dict[str, Any]

    raw_created: bool
    normalized_created: bool


def _require_positive_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
    ):
        raise TypeError(
            f"{field_name} must be an integer."
        )

    if value < 1:
        raise ValueError(
            f"{field_name} must be greater than zero."
        )

    return value


def _require_dictionary(
    value: object,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{field_name} must be a dictionary."
        )

    return value


def _require_nonempty_text(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def _optional_text(
    value: object,
) -> str | None:
    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "Optional text value must be a string."
        )

    normalized = value.strip()

    return normalized or None


def _require_datetime(
    value: object,
    *,
    field_name: str,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        return value

    text = _require_nonempty_text(
        value,
        field_name=field_name,
    )

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        return datetime.fromisoformat(
            text
        )

    except ValueError as error:
        raise ValueError(
            f"{field_name} must contain "
            "an ISO-8601 datetime."
        ) from error


def _require_uuid(
    value: object,
    *,
    field_name: str,
) -> UUID:
    try:
        return UUID(
            str(
                value
            )
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"{field_name} must contain "
            "a valid UUID."
        ) from error


class MarketInformationEvidenceBridge:
    """
    Convert an existing Market Intelligence source_text
    record into Evidence.

    build():
        Create Evidence objects in memory.

    persist():
        Store Evidence in the existing Data Engine.

    Repeated persistence of the same source record
    reuses existing Evidence instead of creating
    duplicate records.
    """

    def __init__(
        self,
        *,
        query_service: QueryService | None = None,
    ) -> None:
        self.query_service = (
            query_service
            if query_service is not None
            else QueryService(
                get_backend()
            )
        )

        self.writer = DataEngineRecordWriter(
            query_service=self.query_service
        )

    def _source_record(
        self,
        source_record_id: int,
    ) -> dict[str, Any]:
        record_id = _require_positive_integer(
            source_record_id,
            field_name="source_record_id",
        )

        record = (
            self.query_service
            .get_record_by_id(
                record_id
            )
        )

        if not isinstance(
            record,
            dict,
        ):
            raise ValueError(
                "Source Data Engine record "
                "was not found."
            )

        if (
            record.get(
                "source"
            )
            != "market_intelligence"
        ):
            raise ValueError(
                "Record is not owned by "
                "Market Intelligence."
            )

        if (
            record.get(
                "data_type"
            )
            != SOURCE_TEXT_DATA_TYPE
        ):
            raise ValueError(
                "Record is not source_text."
            )

        return record

    def _source_value(
        self,
        source_record_id: int,
    ) -> dict[str, Any]:
        record = self._source_record(
            source_record_id
        )

        return _require_dictionary(
            record.get(
                "value"
            ),
            field_name=(
                "source record value"
            ),
        )

    def build(
        self,
        source_record_id: int,
    ) -> EvidenceBridgeResult:
        value = self._source_value(
            source_record_id
        )

        retrieved_text = (
            _require_nonempty_text(
                value.get(
                    "retrieved_text"
                ),
                field_name=(
                    "retrieved_text"
                ),
            )
        )

        source_name = (
            _require_nonempty_text(
                value.get(
                    "source_name"
                ),
                field_name=(
                    "source_name"
                ),
            )
        )

        source_type = (
            _require_nonempty_text(
                value.get(
                    "source_type"
                ),
                field_name=(
                    "source_type"
                ),
            )
        )

        collected_at = (
            _require_datetime(
                value.get(
                    "collected_at"
                ),
                field_name=(
                    "collected_at"
                ),
            )
        )

        source_url = _optional_text(
            value.get(
                "source_url"
            )
        )

        provider_record_id = (
            _optional_text(
                value.get(
                    "record_id"
                )
            )
        )

        metadata = value.get(
            "metadata"
        )

        if metadata is None:
            metadata = {}

        metadata = _require_dictionary(
            metadata,
            field_name="metadata",
        )

        raw_information = RawInformation(
            source_id=(
                provider_record_id
                or str(
                    source_record_id
                )
            ),
            source_type=source_type,
            raw_text=retrieved_text,
            url=source_url,
            retrieved_at=collected_at,
            metadata={
                **metadata,
                "source_name": (
                    source_name
                ),
                "data_engine_source_record_id": (
                    source_record_id
                ),
            },
        )

        normalized_information = (
            NormalizedInformation(
                raw_information_id=(
                    raw_information.id
                ),
                normalized_text=(
                    retrieved_text
                ),
                language=None,
            )
        )

        return EvidenceBridgeResult(
            source_record_id=(
                source_record_id
            ),
            raw_information=(
                raw_information
            ),
            normalized_information=(
                normalized_information
            ),
            raw_record=(
                serialize_entity(
                    raw_information
                )
            ),
            normalized_record=(
                serialize_entity(
                    normalized_information
                )
            ),
        )

    def _existing_raw(
        self,
        source_record_id: int,
    ) -> dict[str, Any] | None:
        matches = []

        for record in (
            self.query_service
            .get_all_records()
        ):
            if not isinstance(
                record,
                dict,
            ):
                continue

            if (
                record.get(
                    "category"
                )
                != STRUCTURED_KNOWLEDGE_DATA_TYPE
            ):
                continue

            if (
                record.get(
                    "data_type"
                )
                != RAW_INFORMATION_DATA_TYPE
            ):
                continue

            value = record.get(
                "value"
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            metadata = value.get(
                "metadata"
            )

            if not isinstance(
                metadata,
                dict,
            ):
                continue

            if (
                metadata.get(
                    "data_engine_source_record_id"
                )
                == source_record_id
            ):
                matches.append(
                    record
                )

        if len(
            matches
        ) > 1:
            raise RuntimeError(
                "Duplicate RawInformation Evidence "
                "exists for the same source record."
            )

        return (
            matches[0]
            if matches
            else None
        )

    def _existing_normalized(
        self,
        raw_information_id: UUID,
    ) -> dict[str, Any] | None:
        matches = []

        wanted = str(
            raw_information_id
        )

        for record in (
            self.query_service
            .get_all_records()
        ):
            if not isinstance(
                record,
                dict,
            ):
                continue

            if (
                record.get(
                    "category"
                )
                != STRUCTURED_KNOWLEDGE_DATA_TYPE
            ):
                continue

            if (
                record.get(
                    "data_type"
                )
                != NORMALIZED_INFORMATION_DATA_TYPE
            ):
                continue

            value = record.get(
                "value"
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            if str(
                value.get(
                    "raw_information_id",
                    "",
                )
            ) == wanted:
                matches.append(
                    record
                )

        if len(
            matches
        ) > 1:
            raise RuntimeError(
                "Duplicate NormalizedInformation "
                "Evidence exists."
            )

        return (
            matches[0]
            if matches
            else None
        )

    def _write_evidence(
        self,
        serialized: dict[str, Any],
        *,
        source_record_id: int,
    ) -> dict[str, Any]:
        value = _require_dictionary(
            serialized.get(
                "value"
            ),
            field_name=(
                "Evidence value"
            ),
        )

        return self.writer.write(
            source=_require_nonempty_text(
                serialized.get(
                    "source"
                ),
                field_name="source",
            ),
            category=(
                STRUCTURED_KNOWLEDGE_DATA_TYPE
            ),
            data_type=(
                _require_nonempty_text(
                    serialized.get(
                        "data_type"
                    ),
                    field_name="data_type",
                )
            ),
            value=value,
            unit="record",
            metadata={
                "source_record_id": (
                    source_record_id
                ),
                "evidence_entity_id": (
                    serialized.get(
                        "id"
                    )
                ),
            },
        )

    def persist(
        self,
        source_record_id: int,
    ) -> EvidencePersistenceResult:
        source_record_id = (
            _require_positive_integer(
                source_record_id,
                field_name=(
                    "source_record_id"
                ),
            )
        )

        source_value = (
            self._source_value(
                source_record_id
            )
        )

        existing_raw = (
            self._existing_raw(
                source_record_id
            )
        )

        if existing_raw is None:
            built = self.build(
                source_record_id
            )

            raw_record = (
                self._write_evidence(
                    built.raw_record,
                    source_record_id=(
                        source_record_id
                    ),
                )
            )

            raw_information_id = (
                built.raw_information.id
            )

            raw_created = True

        else:
            raw_record = existing_raw

            raw_value = (
                _require_dictionary(
                    existing_raw.get(
                        "value"
                    ),
                    field_name=(
                        "RawInformation value"
                    ),
                )
            )

            raw_information_id = (
                _require_uuid(
                    raw_value.get(
                        "id"
                    ),
                    field_name=(
                        "RawInformation id"
                    ),
                )
            )

            raw_created = False

        existing_normalized = (
            self._existing_normalized(
                raw_information_id
            )
        )

        if existing_normalized is None:
            retrieved_text = (
                _require_nonempty_text(
                    source_value.get(
                        "retrieved_text"
                    ),
                    field_name=(
                        "retrieved_text"
                    ),
                )
            )

            normalized = (
                NormalizedInformation(
                    raw_information_id=(
                        raw_information_id
                    ),
                    normalized_text=(
                        retrieved_text
                    ),
                    language=None,
                )
            )

            normalized_record = (
                self._write_evidence(
                    serialize_entity(
                        normalized
                    ),
                    source_record_id=(
                        source_record_id
                    ),
                )
            )

            normalized_created = True

        else:
            normalized_record = (
                existing_normalized
            )

            normalized_created = False

        return EvidencePersistenceResult(
            source_record_id=(
                source_record_id
            ),
            raw_data_engine_record=(
                raw_record
            ),
            normalized_data_engine_record=(
                normalized_record
            ),
            raw_created=(
                raw_created
            ),
            normalized_created=(
                normalized_created
            ),
        )
