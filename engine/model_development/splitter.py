from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from engine.model_development.models import (
    DatasetSplit,
)


DEFAULT_SPLIT_SEED = (
    "dataset-split-v1"
)

DEFAULT_EVALUATION_RATIO = 0.20


def _require_positive_integer(
    value: int,
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


def _require_split_seed(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "split_seed must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            "split_seed must not be empty."
        )

    return normalized


def _require_evaluation_ratio(
    value: float,
) -> float:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise TypeError(
            "evaluation_ratio must be numeric."
        )

    normalized = float(
        value
    )

    if not (
        0.0
        < normalized
        < 1.0
    ):
        raise ValueError(
            "evaluation_ratio must be "
            "greater than 0 and less than 1."
        )

    return normalized


@dataclass(
    frozen=True,
    kw_only=True,
)
class CandidateSplitAssignment:
    candidate_record_id: int

    source_record_id: int

    split: DatasetSplit

    source_group_hash: str


class DeterministicDatasetSplitter:
    """
    Deterministically assign eligible training candidates
    to train or evaluation partitions.

    Candidate records sharing the same source_record_id
    are treated as one source group and must always receive
    the same split.

    Split assignment is derived from SHA-256 hashes of:

        split_seed + source_record_id

    The splitter does not:
    - determine training eligibility;
    - modify Data Engine records;
    - build datasets;
    - materialize JSONL files;
    - start training.
    """

    def __init__(
        self,
        *,
        split_seed: str = (
            DEFAULT_SPLIT_SEED
        ),
        evaluation_ratio: float = (
            DEFAULT_EVALUATION_RATIO
        ),
    ) -> None:
        self.split_seed = (
            _require_split_seed(
                split_seed
            )
        )

        self.evaluation_ratio = (
            _require_evaluation_ratio(
                evaluation_ratio
            )
        )

    def source_group_hash(
        self,
        source_record_id: int,
    ) -> str:
        normalized_source_id = (
            _require_positive_integer(
                source_record_id,
                field_name=(
                    "source_record_id"
                ),
            )
        )

        material = (
            f"{self.split_seed}:"
            f"{normalized_source_id}"
        )

        return hashlib.sha256(
            material.encode(
                "utf-8"
            )
        ).hexdigest()

    def split(
        self,
        candidate_source_records: Mapping[
            int,
            int,
        ],
    ) -> tuple[
        CandidateSplitAssignment,
        ...,
    ]:
        if not isinstance(
            candidate_source_records,
            Mapping,
        ):
            raise TypeError(
                "candidate_source_records must "
                "be a mapping."
            )

        if len(
            candidate_source_records
        ) < 2:
            raise ValueError(
                "At least two candidate records "
                "are required."
            )

        normalized: dict[
            int,
            int,
        ] = {}

        for (
            candidate_record_id,
            source_record_id,
        ) in candidate_source_records.items():
            normalized_candidate_id = (
                _require_positive_integer(
                    candidate_record_id,
                    field_name=(
                        "candidate_record_id"
                    ),
                )
            )

            normalized_source_id = (
                _require_positive_integer(
                    source_record_id,
                    field_name=(
                        "source_record_id"
                    ),
                )
            )

            normalized[
                normalized_candidate_id
            ] = normalized_source_id

        groups: dict[
            int,
            list[int],
        ] = defaultdict(
            list
        )

        for (
            candidate_record_id,
            source_record_id,
        ) in normalized.items():
            groups[
                source_record_id
            ].append(
                candidate_record_id
            )

        if len(
            groups
        ) < 2:
            raise ValueError(
                "At least two unique source records "
                "are required to create independent "
                "training and evaluation partitions."
            )

        source_groups = []

        for source_record_id in groups:
            source_groups.append(
                (
                    self.source_group_hash(
                        source_record_id
                    ),
                    source_record_id,
                )
            )

        source_groups.sort()

        evaluation_group_count = (
            math.ceil(
                len(
                    source_groups
                )
                * self.evaluation_ratio
            )
        )

        evaluation_group_count = max(
            1,
            min(
                evaluation_group_count,
                len(
                    source_groups
                )
                - 1,
            ),
        )

        evaluation_sources = {
            source_record_id
            for (
                _,
                source_record_id,
            )
            in source_groups[
                :evaluation_group_count
            ]
        }

        assignments: list[
            CandidateSplitAssignment
        ] = []

        for candidate_record_id in sorted(
            normalized
        ):
            source_record_id = normalized[
                candidate_record_id
            ]

            split = (
                DatasetSplit.EVALUATION
                if source_record_id
                in evaluation_sources
                else DatasetSplit.TRAIN
            )

            assignments.append(
                CandidateSplitAssignment(
                    candidate_record_id=(
                        candidate_record_id
                    ),
                    source_record_id=(
                        source_record_id
                    ),
                    split=split,
                    source_group_hash=(
                        self.source_group_hash(
                            source_record_id
                        )
                    ),
                )
            )

        self._verify_assignments(
            assignments
        )

        return tuple(
            assignments
        )

    @staticmethod
    def _verify_assignments(
        assignments: list[
            CandidateSplitAssignment
        ],
    ) -> None:
        source_splits: dict[
            int,
            DatasetSplit,
        ] = {}

        train_count = 0
        evaluation_count = 0

        for assignment in assignments:
            previous = source_splits.get(
                assignment.source_record_id
            )

            if (
                previous is not None
                and previous
                != assignment.split
            ):
                raise RuntimeError(
                    "Source record appeared in both "
                    "training and evaluation splits."
                )

            source_splits[
                assignment.source_record_id
            ] = assignment.split

            if (
                assignment.split
                == DatasetSplit.TRAIN
            ):
                train_count += 1

            elif (
                assignment.split
                == DatasetSplit.EVALUATION
            ):
                evaluation_count += 1

        if train_count < 1:
            raise RuntimeError(
                "Training split is empty."
            )

        if evaluation_count < 1:
            raise RuntimeError(
                "Evaluation split is empty."
            )

    def split_by_candidate_id(
        self,
        candidate_source_records: Mapping[
            int,
            int,
        ],
    ) -> dict[
        int,
        DatasetSplit,
    ]:
        assignments = self.split(
            candidate_source_records
        )

        return {
            assignment.candidate_record_id: (
                assignment.split
            )
            for assignment
            in assignments
        }
