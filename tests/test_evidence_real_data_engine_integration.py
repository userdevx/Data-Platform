from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from engine.data_engine.evidence_binding import (
    build_evidence_repository,
)
from engine.evidence.models import (
    RawInformation,
)
from engine.query import QueryService
from engine.storage.json_backend import (
    LocalJsonStorageBackend,
)


def build_real_repository(
    tmp_path: Path,
):
    backend = LocalJsonStorageBackend(
        str(
            tmp_path
            / "records.json"
        )
    )

    query_service = QueryService(
        backend
    )

    return build_evidence_repository(
        query_service=query_service,
    )


def test_raw_information_round_trip_through_real_data_engine(
    tmp_path: Path,
) -> None:
    repo = build_real_repository(
        tmp_path
    )

    original = RawInformation(
        source_id=str(
            uuid4()
        ),
        source_type="configured_source",
        raw_text="runtime evidence record",
    )

    repo.save(
        original
    )

    restored = repo.get(
        original.id
    )

    assert restored == original
    assert restored.id == original.id
