from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from engine.model_development.data_engine import (
    ModelDevelopmentDataEngine,
)
from engine.model_development.models import (
    TrainingCandidate,
    serialize_model_entity,
)


TRAINING_CANDIDATE_DATA_TYPE = (
    "training_candidate"
)

TRAINING_CANDIDATE_STATUS_PROPOSED = (
    "proposed"
)


def _require_nonempty_text(
    value: str,
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


def _normalize_evidence_ids(
    evidence_ids: tuple[
        UUID,
        ...,
    ],
) -> tuple[
    UUID,
    ...,
]:
    if not isinstance(
        evidence_ids,
        tuple,
    ):
        raise TypeError(
            "evidence_ids must be a tuple."
        )

    if not evidence_ids:
        raise ValueError(
            "At least one Evidence ID is required."
        )

    normalized: list[
        UUID
    ] = []

    seen: set[
        UUID
    ] = set()

    for evidence_id in evidence_ids:
        if not isinstance(
            evidence_id,
            UUID,
        ):
            raise TypeError(
                "Every Evidence ID must be a UUID."
            )

        if evidence_id in seen:
            continue

        seen.add(
            evidence_id
        )

        normalized.append(
            evidence_id
        )

    return tuple(
        normalized
    )


def build_candidate_content_hash(
    *,
    source_record_id: int,
    input_text: str,
    target_text: str,
    evidence_ids: tuple[
        UUID,
        ...,
    ],
) -> str:
    """
    Build deterministic identity for candidate content.

    This is used for duplicate detection.

    Runtime timestamps and generated candidate UUIDs are
    deliberately excluded so that the same candidate
    content produces the same hash.
    """

    payload = {
        "source_record_id": (
            source_record_id
        ),
        "input_text": (
            input_text
        ),
        "target_text": (
            target_text
        ),
        "evidence_ids": sorted(
            str(
                evidence_id
            )
            for evidence_id
            in evidence_ids
        ),
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


class TrainingCandidateService:
    """
    Explicit boundary for creating training candidates.

    Creating a candidate does not make information
    training-eligible.

    Every candidate must reference:
    - one existing Data Engine source record;
    - at least one permitted Evidence entity;
    - explicit input and target text.
    """

    def __init__(
        self,
        *,
        data_engine: (
            ModelDevelopmentDataEngine
            | None
        ) = None,
    ) -> None:
        self.data_engine = (
            data_engine
            if data_engine is not None
            else ModelDevelopmentDataEngine()
        )

    def create_candidate(
        self,
        *,
        source_record_id: int,
        input_text: str,
        target_text: str,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        submitted_by: str,
    ) -> dict[str, Any]:
        if not isinstance(
            source_record_id,
            int,
        ):
            raise TypeError(
                "source_record_id must be "
                "an integer."
            )

        if source_record_id < 1:
            raise ValueError(
                "source_record_id must be "
                "greater than zero."
            )

        normalized_input = (
            _require_nonempty_text(
                input_text,
                field_name="input_text",
            )
        )

        normalized_target = (
            _require_nonempty_text(
                target_text,
                field_name="target_text",
            )
        )

        normalized_submitter = (
            _require_nonempty_text(
                submitted_by,
                field_name="submitted_by",
            )
        )

        normalized_evidence_ids = (
            _normalize_evidence_ids(
                evidence_ids
            )
        )

        source_record = (
            self.data_engine
            .get_record(
                source_record_id
            )
        )

        if not isinstance(
            source_record,
            dict,
        ):
            raise TypeError(
                "Source Data Engine record "
                "must be a dictionary."
            )

        for evidence_id in (
            normalized_evidence_ids
        ):
            evidence_record = (
                self.data_engine
                .find_evidence_record(
                    evidence_id
                )
            )

            if evidence_record is None:
                raise ValueError(
                    "Training Evidence was not "
                    "found or is not an allowed "
                    "Evidence type: "
                    f"{evidence_id}"
                )

        content_hash = (
            build_candidate_content_hash(
                source_record_id=(
                    source_record_id
                ),
                input_text=(
                    normalized_input
                ),
                target_text=(
                    normalized_target
                ),
                evidence_ids=(
                    normalized_evidence_ids
                ),
            )
        )

        duplicate = (
            self.data_engine
            .find_model_value(
                data_type=(
                    TRAINING_CANDIDATE_DATA_TYPE
                ),
                field_name="content_hash",
                field_value=content_hash,
            )
        )

        if duplicate is not None:
            raise ValueError(
                "An identical training candidate "
                "already exists."
            )

        candidate = TrainingCandidate(
            source_record_id=(
                source_record_id
            ),
            input_text=(
                normalized_input
            ),
            target_text=(
                normalized_target
            ),
            evidence_ids=(
                normalized_evidence_ids
            ),
            validation_record_ids=(),
            submitted_by=(
                normalized_submitter
            ),
            content_hash=(
                content_hash
            ),
        )

        candidate_value = (
            serialize_model_entity(
                candidate
            )
        )

        stored = (
            self.data_engine
            .write(
                data_type=(
                    TRAINING_CANDIDATE_DATA_TYPE
                ),
                value=(
                    candidate_value
                ),
                metadata={
                    "candidate_status": (
                        TRAINING_CANDIDATE_STATUS_PROPOSED
                    ),
                    "training_eligible": False,
                },
            )
        )

        return stored
