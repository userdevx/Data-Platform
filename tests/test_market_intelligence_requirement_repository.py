from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest

from engine.market_intelligence.models import (
    ProductRequirement,
)
from engine.market_intelligence.requirement_repository import (
    ProductRequirementRepository,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


class MemoryQueryService:
    def __init__(
        self,
        records=None,
    ) -> None:
        self.records = list(
            records or []
        )

    def get_all_records(
        self,
    ):
        return deepcopy(
            self.records
        )


class MemoryWriter:
    def __init__(
        self,
        query_service: MemoryQueryService,
    ) -> None:
        self.query_service = (
            query_service
        )

    def write(
        self,
        requirement: ProductRequirement,
    ):
        payload = (
            requirement
            .to_data_engine_record()
        )

        record = {
            "id":
                len(
                    self.query_service.records
                )
                + 1,
            **payload,
        }

        self.query_service.records.append(
            deepcopy(
                record
            )
        )

        return deepcopy(
            record
        )


def create_requirement(
    *,
    category: str | None = None,
    description: str | None = None,
    priority: int = 3,
    confidence: float = 0.8,
) -> ProductRequirement:
    return ProductRequirement.create(
        category=(
            category
            if category is not None
            else runtime_value(
                "category"
            )
        ),
        description=(
            description
            if description is not None
            else runtime_value(
                "description"
            )
        ),
        priority=priority,
        evidence_topics=[
            runtime_value(
                "topic"
            )
        ],
        trend_ids=[
            runtime_value(
                "trend"
            )
        ],
        confidence=confidence,
    )


def create_repository(
    records=None,
):
    query_service = (
        MemoryQueryService(
            records=records
        )
    )

    writer = MemoryWriter(
        query_service
    )

    repository = (
        ProductRequirementRepository(
            query_service=query_service,
            writer=writer,
        )
    )

    return (
        repository,
        query_service,
    )


def stored_record(
    requirement: ProductRequirement,
):
    return {
        "id": 1,
        **requirement.to_data_engine_record(),
    }


def test_store_requirement():
    repository, _ = (
        create_repository()
    )

    requirement = (
        create_requirement()
    )

    stored = repository.store(
        requirement
    )

    assert (
        stored["source"]
        == "product_intelligence"
    )

    assert (
        stored["category"]
        == "application_requirement"
    )

    assert (
        stored["value"][
            "requirement_id"
        ]
        == requirement.requirement_id
    )


def test_store_rejects_non_requirement():
    repository, _ = (
        create_repository()
    )

    with pytest.raises(
        TypeError
    ):
        repository.store(
            {
                "description":
                    runtime_value(
                        "description"
                    )
            }
        )


def test_get_all_returns_requirements():
    requirement = (
        create_requirement()
    )

    repository, _ = (
        create_repository(
            [
                stored_record(
                    requirement
                )
            ]
        )
    )

    results = repository.get_all()

    assert len(results) == 1

    assert isinstance(
        results[0],
        ProductRequirement,
    )

    assert (
        results[0].requirement_id
        == requirement.requirement_id
    )


def test_get_all_ignores_unrelated_records():
    unrelated = {
        "id": 1,
        "source":
            runtime_value(
                "source"
            ),
        "category":
            runtime_value(
                "category"
            ),
        "data_type":
            runtime_value(
                "data-type"
            ),
        "value": {},
        "unit":
            runtime_value(
                "unit"
            ),
    }

    repository, _ = (
        create_repository(
            [
                unrelated
            ]
        )
    )

    assert repository.get_all() == []


def test_get_by_requirement_id():
    first = create_requirement()
    second = create_requirement()

    repository, _ = (
        create_repository(
            [
                stored_record(
                    first
                ),
                {
                    "id": 2,
                    **second.to_data_engine_record(),
                },
            ]
        )
    )

    result = (
        repository
        .get_by_requirement_id(
            second.requirement_id
        )
    )

    assert result is not None

    assert (
        result.requirement_id
        == second.requirement_id
    )


def test_get_by_requirement_id_returns_none():
    requirement = (
        create_requirement()
    )

    repository, _ = (
        create_repository(
            [
                stored_record(
                    requirement
                )
            ]
        )
    )

    result = (
        repository
        .get_by_requirement_id(
            runtime_value(
                "missing"
            )
        )
    )

    assert result is None


def test_empty_requirement_id_is_rejected():
    repository, _ = (
        create_repository()
    )

    with pytest.raises(
        ValueError
    ):
        repository.get_by_requirement_id(
            "   "
        )


def test_round_trip_preserves_fields():
    repository, _ = (
        create_repository()
    )

    requirement = (
        create_requirement(
            priority=4,
            confidence=0.75,
        )
    )

    repository.store(
        requirement
    )

    loaded = (
        repository
        .get_by_requirement_id(
            requirement.requirement_id
        )
    )

    assert loaded is not None

    assert (
        loaded.requirement_id
        == requirement.requirement_id
    )

    assert (
        loaded.category
        == requirement.category
    )

    assert (
        loaded.description
        == requirement.description
    )

    assert (
        loaded.priority
        == requirement.priority
    )

    assert (
        loaded.evidence_topics
        == requirement.evidence_topics
    )

    assert (
        loaded.trend_ids
        == requirement.trend_ids
    )

    assert (
        loaded.confidence
        == requirement.confidence
    )

    assert (
        loaded.created_at
        == requirement.created_at
    )


def test_missing_stored_field_is_rejected():
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"].pop(
        "description"
    )

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        ValueError
    ):
        repository.get_all()


def test_non_dictionary_value_is_rejected():
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record[
        "value"
    ] = runtime_value(
        "invalid"
    )

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        ValueError
    ):
        repository.get_all()


def test_invalid_priority_type_is_rejected():
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"][
        "priority"
    ] = True

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        TypeError
    ):
        repository.get_all()


@pytest.mark.parametrize(
    "priority",
    [
        0,
        6,
    ],
)
def test_invalid_priority_range_is_rejected(
    priority: int,
):
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"][
        "priority"
    ] = priority

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        ValueError
    ):
        repository.get_all()


def test_invalid_confidence_type_is_rejected():
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"][
        "confidence"
    ] = True

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        TypeError
    ):
        repository.get_all()


@pytest.mark.parametrize(
    "confidence",
    [
        -0.01,
        1.01,
    ],
)
def test_invalid_confidence_range_is_rejected(
    confidence: float,
):
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"][
        "confidence"
    ] = confidence

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        ValueError
    ):
        repository.get_all()


def test_invalid_evidence_topics_is_rejected():
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"][
        "evidence_topics"
    ] = runtime_value(
        "invalid"
    )

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        TypeError
    ):
        repository.get_all()


def test_invalid_trend_ids_is_rejected():
    requirement = (
        create_requirement()
    )

    record = stored_record(
        requirement
    )

    record["value"][
        "trend_ids"
    ] = [
        "   "
    ]

    repository, _ = (
        create_repository(
            [
                record
            ]
        )
    )

    with pytest.raises(
        ValueError
    ):
        repository.get_all()
