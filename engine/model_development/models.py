from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from enum import Enum
from typing import Any
from uuid import (
    UUID,
    uuid4,
)


def _now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class DatasetSplit(
    str,
    Enum,
):
    TRAIN = "train"
    EVALUATION = "evaluation"


class DatasetStatus(
    str,
    Enum,
):
    READY = "ready"
    RETIRED = "retired"


class TrainingValidationDecision(
    str,
    Enum,
):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(
    frozen=True,
    kw_only=True,
)
class TrainingCandidate:
    id: UUID = field(
        default_factory=uuid4
    )

    created_at: datetime = field(
        default_factory=_now
    )

    source_record_id: int

    input_text: str
    target_text: str

    evidence_ids: tuple[
        UUID,
        ...,
    ]

    validation_record_ids: tuple[
        int,
        ...,
    ] = ()

    submitted_by: str

    content_hash: str


@dataclass(
    frozen=True,
    kw_only=True,
)
class TrainingCandidateValidation:
    id: UUID = field(
        default_factory=uuid4
    )

    created_at: datetime = field(
        default_factory=_now
    )

    candidate_record_id: int

    decision: TrainingValidationDecision

    validated_by: str

    evidence_ids: tuple[
        UUID,
        ...,
    ]

    supporting_validation_record_ids: tuple[
        int,
        ...,
    ] = ()

    policy_version: str

    reason: str = ""


@dataclass(
    frozen=True,
    kw_only=True,
)
class ModelTrainingExample:
    id: UUID = field(
        default_factory=uuid4
    )

    created_at: datetime = field(
        default_factory=_now
    )

    dataset_id: UUID

    candidate_record_id: int

    source_record_id: int

    training_validation_record_id: int

    source: str

    data_type: str

    input_text: str

    target_text: str

    split: DatasetSplit

    evidence_ids: tuple[
        UUID,
        ...,
    ] = ()

    validation_record_ids: tuple[
        int,
        ...,
    ] = ()

    content_hash: str


@dataclass(
    frozen=True,
    kw_only=True,
)
class DatasetLineage:
    id: UUID = field(
        default_factory=uuid4
    )

    created_at: datetime = field(
        default_factory=_now
    )

    dataset_id: UUID

    candidate_record_ids: tuple[
        int,
        ...,
    ]

    source_record_ids: tuple[
        int,
        ...,
    ]

    training_validation_record_ids: tuple[
        int,
        ...,
    ]

    evidence_ids: tuple[
        UUID,
        ...,
    ]

    selection_policy_version: str

    split_seed: str


@dataclass(
    frozen=True,
    kw_only=True,
)
class ModelTrainingDataset:
    id: UUID = field(
        default_factory=uuid4
    )

    created_at: datetime = field(
        default_factory=_now
    )

    name: str

    version: int

    selection_policy_version: str

    split_seed: str

    evaluation_ratio: float

    candidate_record_ids: tuple[
        int,
        ...,
    ]

    source_record_ids: tuple[
        int,
        ...,
    ]

    training_example_ids: tuple[
        UUID,
        ...,
    ]

    evaluation_example_ids: tuple[
        UUID,
        ...,
    ]

    training_examples: int

    evaluation_examples: int

    content_hash: str

    status: DatasetStatus = (
        DatasetStatus.READY
    )


def serialize_model_entity(
    entity: object,
) -> dict[str, Any]:
    def encode(
        value: Any,
    ) -> Any:
        if isinstance(
            value,
            UUID,
        ):
            return str(
                value
            )

        if isinstance(
            value,
            datetime,
        ):
            return value.isoformat()

        if isinstance(
            value,
            Enum,
        ):
            return value.value

        if isinstance(
            value,
            tuple,
        ):
            return [
                encode(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            list,
        ):
            return [
                encode(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): encode(
                    item
                )
                for key, item
                in value.items()
            }

        return value

    encoded = encode(
        asdict(
            entity
        )
    )

    if not isinstance(
        encoded,
        dict,
    ):
        raise TypeError(
            "Serialized model entity "
            "must be a dictionary."
        )

    return encoded
