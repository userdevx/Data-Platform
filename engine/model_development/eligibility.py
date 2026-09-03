from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from engine.model_development.data_engine import (
    ModelDevelopmentDataEngine,
)
from engine.model_development.validation import (
    TRAINING_CANDIDATE_DATA_TYPE,
    TRAINING_VALIDATION_DATA_TYPE,
    TrainingCandidateValidationService,
)


DEFAULT_TRAINING_POLICY_VERSION = (
    "training-policy-v1"
)


@dataclass(
    frozen=True,
    kw_only=True,
)
class TrainingEligibilityResult:
    candidate_record_id: int

    eligible: bool

    policy_version: str

    validation_record_id: int | None

    evidence_ids: tuple[
        UUID,
        ...,
    ]

    reason: str


class TrainingEligibilityService:
    """
    Determine whether a TrainingCandidate is eligible
    for explicit dataset selection.

    Eligibility is derived from current Data Engine
    evidence and validation records.

    This service does not:
    - modify the TrainingCandidate;
    - automatically select the candidate;
    - create a training dataset;
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

        self.validation_service = (
            TrainingCandidateValidationService(
                data_engine=self.data_engine
            )
        )

    @staticmethod
    def _require_policy_version(
        policy_version: str,
    ) -> str:
        if not isinstance(
            policy_version,
            str,
        ):
            raise TypeError(
                "policy_version must be a string."
            )

        normalized = policy_version.strip()

        if not normalized:
            raise ValueError(
                "policy_version must not be empty."
            )

        return normalized

    @staticmethod
    def _parse_evidence_ids(
        values: object,
    ) -> tuple[
        UUID,
        ...,
    ]:
        if not isinstance(
            values,
            list,
        ):
            raise ValueError(
                "Evidence linkage must be a list."
            )

        if not values:
            raise ValueError(
                "At least one Evidence ID is required."
            )

        normalized: list[
            UUID
        ] = []

        seen: set[
            UUID
        ] = set()

        for value in values:
            try:
                evidence_id = UUID(
                    str(
                        value
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Evidence linkage contains "
                    "an invalid UUID."
                ) from error

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

    def _candidate_record(
        self,
        candidate_record_id: int,
    ) -> dict:
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
                "Candidate record must be "
                "a dictionary."
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

        metadata = record.get(
            "metadata"
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                "TrainingCandidate value "
                "is invalid."
            )

        if not isinstance(
            metadata,
            dict,
        ):
            raise ValueError(
                "TrainingCandidate metadata "
                "is invalid."
            )

        return record

    def _verify_evidence(
        self,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
    ) -> None:
        for evidence_id in evidence_ids:
            evidence_record = (
                self.data_engine
                .find_evidence_record(
                    evidence_id
                )
            )

            if evidence_record is None:
                raise ValueError(
                    "Evidence is missing or "
                    "is not permitted for training: "
                    f"{evidence_id}"
                )

    @staticmethod
    def _record_id(
        record: dict,
    ) -> int:
        record_id = record.get(
            "id"
        )

        if not isinstance(
            record_id,
            int,
        ):
            raise ValueError(
                "Validation record does not have "
                "an integer Data Engine ID."
            )

        return record_id

    def evaluate_candidate(
        self,
        candidate_record_id: int,
        *,
        policy_version: str = (
            DEFAULT_TRAINING_POLICY_VERSION
        ),
    ) -> TrainingEligibilityResult:
        normalized_policy = (
            self._require_policy_version(
                policy_version
            )
        )

        candidate_record = (
            self._candidate_record(
                candidate_record_id
            )
        )

        candidate_value = candidate_record[
            "value"
        ]

        candidate_metadata = candidate_record[
            "metadata"
        ]

        candidate_status = (
            candidate_metadata.get(
                "candidate_status"
            )
        )

        if candidate_status != "proposed":
            return TrainingEligibilityResult(
                candidate_record_id=(
                    candidate_record_id
                ),
                eligible=False,
                policy_version=(
                    normalized_policy
                ),
                validation_record_id=None,
                evidence_ids=(),
                reason=(
                    "Candidate is not in the "
                    "proposed state."
                ),
            )

        # Candidate creation must never directly
        # authorize training.
        if (
            candidate_metadata.get(
                "training_eligible"
            )
            is not False
        ):
            return TrainingEligibilityResult(
                candidate_record_id=(
                    candidate_record_id
                ),
                eligible=False,
                policy_version=(
                    normalized_policy
                ),
                validation_record_id=None,
                evidence_ids=(),
                reason=(
                    "Candidate contains an invalid "
                    "direct eligibility state."
                ),
            )

        candidate_evidence_ids = (
            self._parse_evidence_ids(
                candidate_value.get(
                    "evidence_ids"
                )
            )
        )

        self._verify_evidence(
            candidate_evidence_ids
        )

        submitted_by = (
            candidate_value.get(
                "submitted_by"
            )
        )

        if (
            not isinstance(
                submitted_by,
                str,
            )
            or not submitted_by.strip()
        ):
            raise ValueError(
                "TrainingCandidate submitted_by "
                "is invalid."
            )

        validations = (
            self.validation_service
            .validations_for_candidate(
                candidate_record_id
            )
        )

        applicable: list[
            dict
        ] = []

        for record in validations:
            if (
                record.get(
                    "data_type"
                )
                != TRAINING_VALIDATION_DATA_TYPE
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

            if (
                value.get(
                    "policy_version"
                )
                != normalized_policy
            ):
                continue

            applicable.append(
                record
            )

        if not applicable:
            return TrainingEligibilityResult(
                candidate_record_id=(
                    candidate_record_id
                ),
                eligible=False,
                policy_version=(
                    normalized_policy
                ),
                validation_record_id=None,
                evidence_ids=(
                    candidate_evidence_ids
                ),
                reason=(
                    "No validation exists for "
                    "the requested training policy."
                ),
            )

        # Validation records are append-only Data Engine
        # records. The greatest Data Engine integer ID is
        # the latest applicable lifecycle decision.
        applicable.sort(
            key=self._record_id,
            reverse=True,
        )

        latest_validation = (
            applicable[0]
        )

        latest_record_id = (
            self._record_id(
                latest_validation
            )
        )

        latest_value = (
            latest_validation.get(
                "value"
            )
        )

        if not isinstance(
            latest_value,
            dict,
        ):
            raise ValueError(
                "Latest validation value "
                "is invalid."
            )

        validated_by = (
            latest_value.get(
                "validated_by"
            )
        )

        if (
            not isinstance(
                validated_by,
                str,
            )
            or not validated_by.strip()
        ):
            return TrainingEligibilityResult(
                candidate_record_id=(
                    candidate_record_id
                ),
                eligible=False,
                policy_version=(
                    normalized_policy
                ),
                validation_record_id=(
                    latest_record_id
                ),
                evidence_ids=(
                    candidate_evidence_ids
                ),
                reason=(
                    "Latest validation does not "
                    "contain a valid validator."
                ),
            )

        if (
            validated_by.strip().casefold()
            == submitted_by.strip().casefold()
        ):
            return TrainingEligibilityResult(
                candidate_record_id=(
                    candidate_record_id
                ),
                eligible=False,
                policy_version=(
                    normalized_policy
                ),
                validation_record_id=(
                    latest_record_id
                ),
                evidence_ids=(
                    candidate_evidence_ids
                ),
                reason=(
                    "Latest validation is not "
                    "independent."
                ),
            )

        validation_evidence_ids = (
            self._parse_evidence_ids(
                latest_value.get(
                    "evidence_ids"
                )
            )
        )

        self._verify_evidence(
            validation_evidence_ids
        )

        decision = latest_value.get(
            "decision"
        )

        if decision != "approved":
            return TrainingEligibilityResult(
                candidate_record_id=(
                    candidate_record_id
                ),
                eligible=False,
                policy_version=(
                    normalized_policy
                ),
                validation_record_id=(
                    latest_record_id
                ),
                evidence_ids=(
                    validation_evidence_ids
                ),
                reason=(
                    "Latest applicable validation "
                    "is not approved."
                ),
            )

        return TrainingEligibilityResult(
            candidate_record_id=(
                candidate_record_id
            ),
            eligible=True,
            policy_version=(
                normalized_policy
            ),
            validation_record_id=(
                latest_record_id
            ),
            evidence_ids=(
                validation_evidence_ids
            ),
            reason=(
                "Candidate has permitted Evidence "
                "and an approved independent "
                "validation for the requested "
                "training policy."
            ),
        )

    def require_eligible(
        self,
        candidate_record_id: int,
        *,
        policy_version: str = (
            DEFAULT_TRAINING_POLICY_VERSION
        ),
    ) -> TrainingEligibilityResult:
        result = self.evaluate_candidate(
            candidate_record_id,
            policy_version=(
                policy_version
            ),
        )

        if not result.eligible:
            raise ValueError(
                "TrainingCandidate is not eligible: "
                f"{result.reason}"
            )

        return result
