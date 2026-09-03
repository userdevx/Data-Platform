from __future__ import annotations

from typing import Any
from uuid import UUID

from engine.model_development.data_engine import (
    ModelDevelopmentDataEngine,
)
from engine.model_development.models import (
    TrainingCandidateValidation,
    TrainingValidationDecision,
    serialize_model_entity,
)


TRAINING_CANDIDATE_DATA_TYPE = (
    "training_candidate"
)

TRAINING_VALIDATION_DATA_TYPE = (
    "training_candidate_validation"
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


def _normalize_record_ids(
    record_ids: tuple[
        int,
        ...,
    ],
) -> tuple[
    int,
    ...,
]:
    if not isinstance(
        record_ids,
        tuple,
    ):
        raise TypeError(
            "supporting_validation_record_ids "
            "must be a tuple."
        )

    normalized: list[
        int
    ] = []

    seen: set[
        int
    ] = set()

    for record_id in record_ids:
        if not isinstance(
            record_id,
            int,
        ):
            raise TypeError(
                "Every supporting validation "
                "record ID must be an integer."
            )

        if record_id < 1:
            raise ValueError(
                "Supporting validation record "
                "IDs must be greater than zero."
            )

        if record_id in seen:
            continue

        seen.add(
            record_id
        )

        normalized.append(
            record_id
        )

    return tuple(
        normalized
    )


class TrainingCandidateValidationService:
    """
    Independent validation boundary for training
    candidates.

    Validation creates an append-only lifecycle record.

    It does not:
    - modify the source record;
    - modify the TrainingCandidate;
    - mark the candidate training-eligible;
    - build a dataset;
    - start model training.
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

    def _candidate_record(
        self,
        candidate_record_id: int,
    ) -> dict[str, Any]:
        if not isinstance(
            candidate_record_id,
            int,
        ):
            raise TypeError(
                "candidate_record_id must be "
                "an integer."
            )

        if candidate_record_id < 1:
            raise ValueError(
                "candidate_record_id must be "
                "greater than zero."
            )

        record = self.data_engine.get_record(
            candidate_record_id
        )

        if not isinstance(
            record,
            dict,
        ):
            raise TypeError(
                "Candidate Data Engine record "
                "must be a dictionary."
            )

        if (
            record.get(
                "source"
            )
            != self.data_engine.SOURCE
        ):
            raise ValueError(
                "Record is not owned by "
                "model development."
            )

        if (
            record.get(
                "data_type"
            )
            != TRAINING_CANDIDATE_DATA_TYPE
        ):
            raise ValueError(
                "Record is not a "
                "TrainingCandidate."
            )

        value = record.get(
            "value"
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                "TrainingCandidate value "
                "is invalid."
            )

        return record

    def record_validation(
        self,
        *,
        candidate_record_id: int,
        decision: TrainingValidationDecision,
        validated_by: str,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        policy_version: str,
        reason: str = "",
        supporting_validation_record_ids: tuple[
            int,
            ...,
        ] = (),
    ) -> dict[str, Any]:
        if not isinstance(
            decision,
            TrainingValidationDecision,
        ):
            raise TypeError(
                "decision must be a "
                "TrainingValidationDecision."
            )

        normalized_validator = (
            _require_nonempty_text(
                validated_by,
                field_name="validated_by",
            )
        )

        normalized_policy = (
            _require_nonempty_text(
                policy_version,
                field_name="policy_version",
            )
        )

        if not isinstance(
            reason,
            str,
        ):
            raise TypeError(
                "reason must be a string."
            )

        normalized_reason = (
            reason.strip()
        )

        normalized_evidence_ids = (
            _normalize_evidence_ids(
                evidence_ids
            )
        )

        normalized_supporting_ids = (
            _normalize_record_ids(
                supporting_validation_record_ids
            )
        )

        candidate_record = (
            self._candidate_record(
                candidate_record_id
            )
        )

        candidate_value = (
            candidate_record[
                "value"
            ]
        )

        submitted_by = (
            candidate_value.get(
                "submitted_by"
            )
        )

        if not isinstance(
            submitted_by,
            str,
        ):
            raise ValueError(
                "TrainingCandidate does not "
                "contain a valid submitted_by."
            )

        if (
            submitted_by.strip().casefold()
            == normalized_validator.casefold()
        ):
            raise ValueError(
                "TrainingCandidate validation "
                "must be independent from the "
                "candidate submitter."
            )

        candidate_evidence = (
            candidate_value.get(
                "evidence_ids"
            )
        )

        if not isinstance(
            candidate_evidence,
            list,
        ):
            raise ValueError(
                "TrainingCandidate Evidence "
                "linkage is invalid."
            )

        if not candidate_evidence:
            raise ValueError(
                "TrainingCandidate has no "
                "Evidence linkage."
            )

        # Re-verify the Evidence originally attached
        # to the candidate. Candidate creation alone
        # must not permanently authorize Evidence.
        for candidate_evidence_id in (
            candidate_evidence
        ):
            try:
                evidence_uuid = UUID(
                    str(
                        candidate_evidence_id
                    )
                )
            except ValueError as error:
                raise ValueError(
                    "TrainingCandidate contains "
                    "an invalid Evidence UUID."
                ) from error

            if (
                self.data_engine
                .find_evidence_record(
                    evidence_uuid
                )
                is None
            ):
                raise ValueError(
                    "TrainingCandidate references "
                    "Evidence that is no longer "
                    "valid for training."
                )

        # Independently verify every Evidence entity
        # explicitly used for this validation.
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
                    "Validation Evidence was not "
                    "found or is not an allowed "
                    "Evidence type: "
                    f"{evidence_id}"
                )

        # Supporting validation records, when used,
        # must already exist in the Data Engine.
        for record_id in (
            normalized_supporting_ids
        ):
            self.data_engine.get_record(
                record_id
            )

        validation = (
            TrainingCandidateValidation(
                candidate_record_id=(
                    candidate_record_id
                ),
                decision=decision,
                validated_by=(
                    normalized_validator
                ),
                evidence_ids=(
                    normalized_evidence_ids
                ),
                supporting_validation_record_ids=(
                    normalized_supporting_ids
                ),
                policy_version=(
                    normalized_policy
                ),
                reason=(
                    normalized_reason
                ),
            )
        )

        validation_value = (
            serialize_model_entity(
                validation
            )
        )

        stored = self.data_engine.write(
            data_type=(
                TRAINING_VALIDATION_DATA_TYPE
            ),
            value=validation_value,
            metadata={
                "candidate_record_id": (
                    candidate_record_id
                ),
                "validation_decision": (
                    decision.value
                ),
                "training_eligibility_changed": (
                    False
                ),
            },
        )

        return stored

    def approve_candidate(
        self,
        *,
        candidate_record_id: int,
        validated_by: str,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        policy_version: str,
        reason: str = "",
        supporting_validation_record_ids: tuple[
            int,
            ...,
        ] = (),
    ) -> dict[str, Any]:
        return self.record_validation(
            candidate_record_id=(
                candidate_record_id
            ),
            decision=(
                TrainingValidationDecision.APPROVED
            ),
            validated_by=(
                validated_by
            ),
            evidence_ids=(
                evidence_ids
            ),
            policy_version=(
                policy_version
            ),
            reason=(
                reason
            ),
            supporting_validation_record_ids=(
                supporting_validation_record_ids
            ),
        )

    def reject_candidate(
        self,
        *,
        candidate_record_id: int,
        validated_by: str,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        policy_version: str,
        reason: str,
        supporting_validation_record_ids: tuple[
            int,
            ...,
        ] = (),
    ) -> dict[str, Any]:
        normalized_reason = (
            _require_nonempty_text(
                reason,
                field_name="reason",
            )
        )

        return self.record_validation(
            candidate_record_id=(
                candidate_record_id
            ),
            decision=(
                TrainingValidationDecision.REJECTED
            ),
            validated_by=(
                validated_by
            ),
            evidence_ids=(
                evidence_ids
            ),
            policy_version=(
                policy_version
            ),
            reason=(
                normalized_reason
            ),
            supporting_validation_record_ids=(
                supporting_validation_record_ids
            ),
        )

    def validations_for_candidate(
        self,
        candidate_record_id: int,
    ) -> list[dict[str, Any]]:
        self._candidate_record(
            candidate_record_id
        )

        records = self.data_engine.records(
            data_type=(
                TRAINING_VALIDATION_DATA_TYPE
            )
        )

        matching: list[
            dict[str, Any]
        ] = []

        for record in records:
            value = record.get(
                "value"
            )

            if not isinstance(
                value,
                dict,
            ):
                continue

            if (
                value.get(
                    "candidate_record_id"
                )
                == candidate_record_id
            ):
                matching.append(
                    record
                )

        return matching
