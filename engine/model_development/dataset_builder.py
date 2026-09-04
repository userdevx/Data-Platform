from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import (
    UUID,
    uuid4,
)

from engine.model_development.candidates import (
    TRAINING_CANDIDATE_DATA_TYPE,
    build_candidate_content_hash,
)
from engine.model_development.data_engine import (
    ModelDevelopmentDataEngine,
)
from engine.model_development.eligibility import (
    DEFAULT_TRAINING_POLICY_VERSION,
    TrainingEligibilityService,
)
from engine.model_development.fingerprints import (
    fingerprint_payload,
)
from engine.model_development.models import (
    DatasetLineage,
    DatasetSplit,
    DatasetStatus,
    ModelTrainingDataset,
    ModelTrainingExample,
    serialize_model_entity,
)
from engine.model_development.splitter import (
    DEFAULT_EVALUATION_RATIO,
    DEFAULT_SPLIT_SEED,
    DeterministicDatasetSplitter,
)
from engine.model_development.validation import (
    TRAINING_VALIDATION_DATA_TYPE,
)


MODEL_TRAINING_EXAMPLE_DATA_TYPE = (
    "model_training_example"
)

DATASET_LINEAGE_DATA_TYPE = (
    "dataset_lineage"
)

MODEL_TRAINING_DATASET_DATA_TYPE = (
    "model_training_dataset"
)


@dataclass(
    frozen=True,
    kw_only=True,
)
class DatasetBuildResult:
    dataset_record: dict[str, Any]

    lineage_record: dict[str, Any]

    training_example_records: tuple[
        dict[str, Any],
        ...,
    ]

    evaluation_example_records: tuple[
        dict[str, Any],
        ...,
    ]


@dataclass(
    frozen=True,
    kw_only=True,
)
class _PreparedCandidate:
    candidate_record_id: int

    source_record_id: int

    source: str

    data_type: str

    input_text: str

    target_text: str

    candidate_content_hash: str

    evidence_ids: tuple[
        UUID,
        ...,
    ]

    training_validation_record_id: int

    validation_record_ids: tuple[
        int,
        ...,
    ]


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


def _parse_uuid_values(
    values: object,
    *,
    field_name: str,
) -> tuple[
    UUID,
    ...,
]:
    if not isinstance(
        values,
        (
            list,
            tuple,
        ),
    ):
        raise ValueError(
            f"{field_name} must contain UUID values."
        )

    normalized: list[
        UUID
    ] = []

    seen: set[
        UUID
    ] = set()

    for value in values:
        try:
            item = UUID(
                str(
                    value
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                f"{field_name} contains "
                "an invalid UUID."
            ) from error

        if item in seen:
            continue

        seen.add(
            item
        )

        normalized.append(
            item
        )

    return tuple(
        normalized
    )


def _parse_record_ids(
    values: object,
    *,
    field_name: str,
) -> tuple[
    int,
    ...,
]:
    if values is None:
        return ()

    if not isinstance(
        values,
        (
            list,
            tuple,
        ),
    ):
        raise ValueError(
            f"{field_name} must contain "
            "Data Engine record IDs."
        )

    normalized: list[
        int
    ] = []

    seen: set[
        int
    ] = set()

    for value in values:
        record_id = (
            _require_positive_integer(
                value,
                field_name=field_name,
            )
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


def _ordered_unique_uuids(
    *groups: tuple[
        UUID,
        ...,
    ],
) -> tuple[
    UUID,
    ...,
]:
    values: set[
        UUID
    ] = set()

    for group in groups:
        values.update(
            group
        )

    return tuple(
        sorted(
            values,
            key=str,
        )
    )


def _ordered_unique_record_ids(
    *groups: tuple[
        int,
        ...,
    ],
) -> tuple[
    int,
    ...,
]:
    values: set[
        int
    ] = set()

    for group in groups:
        values.update(
            group
        )

    return tuple(
        sorted(
            values
        )
    )


class ModelTrainingDatasetBuilder:
    """
    Build a versioned training dataset from an explicit
    set of eligible TrainingCandidate records.

    Candidates are never discovered automatically.

    Before persistence, every selected candidate is
    checked for:

    - Data Engine identity;
    - current training eligibility;
    - source-record lineage;
    - candidate content integrity;
    - approved validation lineage;
    - permitted Evidence;
    - deterministic split assignment.

    Dataset files are not created here. The Data Engine
    remains authoritative.
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

        self.eligibility_service = (
            TrainingEligibilityService(
                data_engine=self.data_engine
            )
        )

    def _candidate_record_ids(
        self,
        values: tuple[
            int,
            ...,
        ],
    ) -> tuple[
        int,
        ...,
    ]:
        if not isinstance(
            values,
            tuple,
        ):
            raise TypeError(
                "candidate_record_ids must "
                "be a tuple."
            )

        if len(
            values
        ) < 2:
            raise ValueError(
                "At least two explicitly selected "
                "candidate records are required."
            )

        normalized: list[
            int
        ] = []

        seen: set[
            int
        ] = set()

        for value in values:
            record_id = (
                _require_positive_integer(
                    value,
                    field_name=(
                        "candidate_record_id"
                    ),
                )
            )

            if record_id in seen:
                raise ValueError(
                    "candidate_record_ids must "
                    "not contain duplicates."
                )

            seen.add(
                record_id
            )

            normalized.append(
                record_id
            )

        return tuple(
            sorted(
                normalized
            )
        )

    @staticmethod
    def _source_data_type(
        record: dict[str, Any],
    ) -> str:
        data_type = record.get(
            "data_type"
        )

        if (
            isinstance(
                data_type,
                str,
            )
            and data_type.strip()
        ):
            return data_type.strip()

        raise ValueError(
            "Source record does not contain "
            "a usable data_type."
        )

    def _prepare_candidate(
        self,
        candidate_record_id: int,
        *,
        policy_version: str,
    ) -> _PreparedCandidate:
        eligibility = (
            self.eligibility_service
            .require_eligible(
                candidate_record_id,
                policy_version=(
                    policy_version
                ),
            )
        )

        if (
            eligibility.validation_record_id
            is None
        ):
            raise RuntimeError(
                "Eligible candidate does not "
                "reference a validation record."
            )

        training_validation_record_id = (
            _require_positive_integer(
                eligibility.validation_record_id,
                field_name=(
                    "training_validation_record_id"
                ),
            )
        )

        candidate_record = (
            self.data_engine
            .get_record(
                candidate_record_id
            )
        )

        if (
            candidate_record.get(
                "source"
            )
            != self.data_engine.SOURCE
        ):
            raise ValueError(
                "Selected record is not owned "
                "by model development."
            )

        if (
            candidate_record.get(
                "data_type"
            )
            != TRAINING_CANDIDATE_DATA_TYPE
        ):
            raise ValueError(
                "Selected record is not a "
                "TrainingCandidate."
            )

        candidate_value = (
            candidate_record.get(
                "value"
            )
        )

        if not isinstance(
            candidate_value,
            dict,
        ):
            raise ValueError(
                "TrainingCandidate value "
                "is invalid."
            )

        source_record_id = (
            _require_positive_integer(
                candidate_value.get(
                    "source_record_id"
                ),
                field_name=(
                    "source_record_id"
                ),
            )
        )

        input_text = (
            _require_nonempty_text(
                candidate_value.get(
                    "input_text"
                ),
                field_name="input_text",
            )
        )

        target_text = (
            _require_nonempty_text(
                candidate_value.get(
                    "target_text"
                ),
                field_name="target_text",
            )
        )

        stored_candidate_hash = (
            _require_nonempty_text(
                candidate_value.get(
                    "content_hash"
                ),
                field_name=(
                    "content_hash"
                ),
            )
        )

        candidate_evidence_ids = (
            _parse_uuid_values(
                candidate_value.get(
                    "evidence_ids"
                ),
                field_name=(
                    "candidate evidence_ids"
                ),
            )
        )

        if not candidate_evidence_ids:
            raise ValueError(
                "TrainingCandidate has no Evidence."
            )

        expected_candidate_hash = (
            build_candidate_content_hash(
                source_record_id=(
                    source_record_id
                ),
                input_text=input_text,
                target_text=target_text,
                evidence_ids=(
                    candidate_evidence_ids
                ),
            )
        )

        if (
            stored_candidate_hash
            != expected_candidate_hash
        ):
            raise ValueError(
                "TrainingCandidate content hash "
                "does not match its current content."
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
            raise ValueError(
                "Source Data Engine record "
                "is invalid."
            )

        source = (
            _require_nonempty_text(
                source_record.get(
                    "source"
                ),
                field_name="source",
            )
        )

        data_type = (
            self._source_data_type(
                source_record
            )
        )

        validation_record = (
            self.data_engine
            .get_record(
                training_validation_record_id
            )
        )

        if (
            validation_record.get(
                "source"
            )
            != self.data_engine.SOURCE
        ):
            raise ValueError(
                "Training validation record "
                "has an invalid owner."
            )

        if (
            validation_record.get(
                "data_type"
            )
            != TRAINING_VALIDATION_DATA_TYPE
        ):
            raise ValueError(
                "Training validation record "
                "has an invalid data_type."
            )

        validation_value = (
            validation_record.get(
                "value"
            )
        )

        if not isinstance(
            validation_value,
            dict,
        ):
            raise ValueError(
                "Training validation value "
                "is invalid."
            )

        if (
            validation_value.get(
                "candidate_record_id"
            )
            != candidate_record_id
        ):
            raise ValueError(
                "Training validation does not "
                "reference the selected candidate."
            )

        if (
            validation_value.get(
                "decision"
            )
            != "approved"
        ):
            raise ValueError(
                "Training validation is not approved."
            )

        if (
            validation_value.get(
                "policy_version"
            )
            != policy_version
        ):
            raise ValueError(
                "Training validation policy "
                "does not match dataset policy."
            )

        validation_evidence_ids = (
            _parse_uuid_values(
                validation_value.get(
                    "evidence_ids"
                ),
                field_name=(
                    "validation evidence_ids"
                ),
            )
        )

        combined_evidence_ids = (
            _ordered_unique_uuids(
                candidate_evidence_ids,
                validation_evidence_ids,
                eligibility.evidence_ids,
            )
        )

        for evidence_id in (
            combined_evidence_ids
        ):
            evidence_record = (
                self.data_engine
                .find_evidence_record(
                    evidence_id
                )
            )

            if evidence_record is None:
                raise ValueError(
                    "Dataset candidate references "
                    "Evidence that is not currently "
                    "permitted for training."
                )

        candidate_validation_ids = (
            _parse_record_ids(
                candidate_value.get(
                    "validation_record_ids",
                    [],
                ),
                field_name=(
                    "candidate validation_record_ids"
                ),
            )
        )

        supporting_validation_ids = (
            _parse_record_ids(
                validation_value.get(
                    "supporting_validation_record_ids",
                    [],
                ),
                field_name=(
                    "supporting_validation_record_ids"
                ),
            )
        )

        validation_record_ids = (
            _ordered_unique_record_ids(
                candidate_validation_ids,
                supporting_validation_ids,
                (
                    training_validation_record_id,
                ),
            )
        )

        for record_id in (
            validation_record_ids
        ):
            self.data_engine.get_record(
                record_id
            )

        return _PreparedCandidate(
            candidate_record_id=(
                candidate_record_id
            ),
            source_record_id=(
                source_record_id
            ),
            source=source,
            data_type=data_type,
            input_text=input_text,
            target_text=target_text,
            candidate_content_hash=(
                stored_candidate_hash
            ),
            evidence_ids=(
                combined_evidence_ids
            ),
            training_validation_record_id=(
                training_validation_record_id
            ),
            validation_record_ids=(
                validation_record_ids
            ),
        )

    def _next_version(
        self,
        *,
        dataset_name: str,
    ) -> int:
        versions: list[
            int
        ] = []

        records = self.data_engine.records(
            data_type=(
                MODEL_TRAINING_DATASET_DATA_TYPE
            )
        )

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
                    "name"
                )
                != dataset_name
            ):
                continue

            version = value.get(
                "version"
            )

            if (
                isinstance(
                    version,
                    int,
                )
                and not isinstance(
                    version,
                    bool,
                )
                and version > 0
            ):
                versions.append(
                    version
                )

        if not versions:
            return 1

        return max(
            versions
        ) + 1

    def build_dataset(
        self,
        *,
        name: str,
        candidate_record_ids: tuple[
            int,
            ...,
        ],
        selection_policy_version: str = (
            DEFAULT_TRAINING_POLICY_VERSION
        ),
        split_seed: str = (
            DEFAULT_SPLIT_SEED
        ),
        evaluation_ratio: float = (
            DEFAULT_EVALUATION_RATIO
        ),
    ) -> DatasetBuildResult:
        dataset_name = (
            _require_nonempty_text(
                name,
                field_name="name",
            )
        )

        policy_version = (
            _require_nonempty_text(
                selection_policy_version,
                field_name=(
                    "selection_policy_version"
                ),
            )
        )

        selected_candidate_ids = (
            self._candidate_record_ids(
                candidate_record_ids
            )
        )

        splitter = (
            DeterministicDatasetSplitter(
                split_seed=split_seed,
                evaluation_ratio=(
                    evaluation_ratio
                ),
            )
        )

        # Complete all candidate validation before
        # writing any dataset lifecycle records.
        prepared_candidates = tuple(
            self._prepare_candidate(
                candidate_record_id,
                policy_version=(
                    policy_version
                ),
            )
            for candidate_record_id
            in selected_candidate_ids
        )

        candidate_source_records = {
            candidate.candidate_record_id: (
                candidate.source_record_id
            )
            for candidate
            in prepared_candidates
        }

        assignments = splitter.split(
            candidate_source_records
        )

        assignment_by_candidate = {
            assignment.candidate_record_id: (
                assignment
            )
            for assignment
            in assignments
        }

        dataset_id = uuid4()

        examples: list[
            ModelTrainingExample
        ] = []

        for candidate in prepared_candidates:
            assignment = (
                assignment_by_candidate[
                    candidate.candidate_record_id
                ]
            )

            example_content_hash = (
                fingerprint_payload(
                    {
                        "candidate_record_id": (
                            candidate
                            .candidate_record_id
                        ),
                        "source_record_id": (
                            candidate
                            .source_record_id
                        ),
                        "training_validation_record_id": (
                            candidate
                            .training_validation_record_id
                        ),
                        "source": (
                            candidate.source
                        ),
                        "data_type": (
                            candidate.data_type
                        ),
                        "input_text": (
                            candidate.input_text
                        ),
                        "target_text": (
                            candidate.target_text
                        ),
                        "split": (
                            assignment.split.value
                        ),
                        "evidence_ids": [
                            str(
                                evidence_id
                            )
                            for evidence_id
                            in candidate.evidence_ids
                        ],
                        "validation_record_ids": list(
                            candidate
                            .validation_record_ids
                        ),
                        "candidate_content_hash": (
                            candidate
                            .candidate_content_hash
                        ),
                    }
                )
            )

            examples.append(
                ModelTrainingExample(
                    dataset_id=(
                        dataset_id
                    ),
                    candidate_record_id=(
                        candidate
                        .candidate_record_id
                    ),
                    source_record_id=(
                        candidate
                        .source_record_id
                    ),
                    training_validation_record_id=(
                        candidate
                        .training_validation_record_id
                    ),
                    source=(
                        candidate.source
                    ),
                    data_type=(
                        candidate.data_type
                    ),
                    input_text=(
                        candidate.input_text
                    ),
                    target_text=(
                        candidate.target_text
                    ),
                    split=(
                        assignment.split
                    ),
                    evidence_ids=(
                        candidate.evidence_ids
                    ),
                    validation_record_ids=(
                        candidate
                        .validation_record_ids
                    ),
                    content_hash=(
                        example_content_hash
                    ),
                )
            )

        training_examples = tuple(
            example
            for example in examples
            if example.split
            == DatasetSplit.TRAIN
        )

        evaluation_examples = tuple(
            example
            for example in examples
            if example.split
            == DatasetSplit.EVALUATION
        )

        if not training_examples:
            raise RuntimeError(
                "Training partition is empty."
            )

        if not evaluation_examples:
            raise RuntimeError(
                "Evaluation partition is empty."
            )

        source_record_ids = tuple(
            sorted(
                {
                    candidate.source_record_id
                    for candidate
                    in prepared_candidates
                }
            )
        )

        training_validation_record_ids = tuple(
            sorted(
                {
                    candidate
                    .training_validation_record_id
                    for candidate
                    in prepared_candidates
                }
            )
        )

        evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for candidate
                    in prepared_candidates
                    for evidence_id
                    in candidate.evidence_ids
                },
                key=str,
            )
        )

        lineage = DatasetLineage(
            dataset_id=dataset_id,
            candidate_record_ids=(
                selected_candidate_ids
            ),
            source_record_ids=(
                source_record_ids
            ),
            training_validation_record_ids=(
                training_validation_record_ids
            ),
            evidence_ids=evidence_ids,
            selection_policy_version=(
                policy_version
            ),
            split_seed=(
                splitter.split_seed
            ),
        )

        dataset_content_hash = (
            fingerprint_payload(
                {
                    "name": (
                        dataset_name
                    ),
                    "selection_policy_version": (
                        policy_version
                    ),
                    "split_seed": (
                        splitter.split_seed
                    ),
                    "evaluation_ratio": (
                        splitter.evaluation_ratio
                    ),
                    "candidate_record_ids": list(
                        selected_candidate_ids
                    ),
                    "source_record_ids": list(
                        source_record_ids
                    ),
                    "examples": [
                        {
                            "candidate_record_id": (
                                example
                                .candidate_record_id
                            ),
                            "source_record_id": (
                                example
                                .source_record_id
                            ),
                            "training_validation_record_id": (
                                example
                                .training_validation_record_id
                            ),
                            "split": (
                                example.split.value
                            ),
                            "content_hash": (
                                example.content_hash
                            ),
                        }
                        for example
                        in examples
                    ],
                }
            )
        )

        version = self._next_version(
            dataset_name=(
                dataset_name
            )
        )

        dataset = ModelTrainingDataset(
            id=dataset_id,
            name=dataset_name,
            version=version,
            selection_policy_version=(
                policy_version
            ),
            split_seed=(
                splitter.split_seed
            ),
            evaluation_ratio=(
                splitter.evaluation_ratio
            ),
            candidate_record_ids=(
                selected_candidate_ids
            ),
            source_record_ids=(
                source_record_ids
            ),
            training_example_ids=tuple(
                example.id
                for example
                in training_examples
            ),
            evaluation_example_ids=tuple(
                example.id
                for example
                in evaluation_examples
            ),
            training_examples=len(
                training_examples
            ),
            evaluation_examples=len(
                evaluation_examples
            ),
            content_hash=(
                dataset_content_hash
            ),
            status=(
                DatasetStatus.READY
            ),
        )

        stored_training_examples: list[
            dict[str, Any]
        ] = []

        stored_evaluation_examples: list[
            dict[str, Any]
        ] = []

        for example in examples:
            stored = self.data_engine.write(
                data_type=(
                    MODEL_TRAINING_EXAMPLE_DATA_TYPE
                ),
                value=(
                    serialize_model_entity(
                        example
                    )
                ),
                metadata={
                    "dataset_id": str(
                        dataset_id
                    ),
                    "candidate_record_id": (
                        example.candidate_record_id
                    ),
                    "source_record_id": (
                        example.source_record_id
                    ),
                    "split": (
                        example.split.value
                    ),
                },
            )

            if (
                example.split
                == DatasetSplit.TRAIN
            ):
                stored_training_examples.append(
                    stored
                )

            else:
                stored_evaluation_examples.append(
                    stored
                )

        lineage_record = (
            self.data_engine.write(
                data_type=(
                    DATASET_LINEAGE_DATA_TYPE
                ),
                value=(
                    serialize_model_entity(
                        lineage
                    )
                ),
                metadata={
                    "dataset_id": str(
                        dataset_id
                    ),
                },
            )
        )

        dataset_record = (
            self.data_engine.write(
                data_type=(
                    MODEL_TRAINING_DATASET_DATA_TYPE
                ),
                value=(
                    serialize_model_entity(
                        dataset
                    )
                ),
                metadata={
                    "dataset_name": (
                        dataset_name
                    ),
                    "dataset_version": (
                        version
                    ),
                    "dataset_status": (
                        DatasetStatus.READY.value
                    ),
                },
            )
        )

        return DatasetBuildResult(
            dataset_record=(
                dataset_record
            ),
            lineage_record=(
                lineage_record
            ),
            training_example_records=tuple(
                stored_training_examples
            ),
            evaluation_example_records=tuple(
                stored_evaluation_examples
            ),
        )
