from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import (
    UUID,
    uuid4,
)

from engine.model_development.data_engine import (
    ModelDevelopmentDataEngine,
)
from engine.model_development.dataset_builder import (
    MODEL_TRAINING_DATASET_DATA_TYPE,
    MODEL_TRAINING_EXAMPLE_DATA_TYPE,
)


DEFAULT_DATASET_OUTPUT_ROOT = Path(
    "data/model_training/datasets"
)


@dataclass(
    frozen=True,
    kw_only=True,
)
class MaterializedDataset:
    dataset_id: UUID

    directory: Path

    train_path: Path

    evaluation_path: Path

    manifest_path: Path

    train_sha256: str

    evaluation_sha256: str

    manifest_sha256: str

    training_examples: int

    evaluation_examples: int


def _sha256_bytes(
    content: bytes,
) -> str:
    return hashlib.sha256(
        content
    ).hexdigest()


def _require_uuid(
    value: UUID | str,
    *,
    field_name: str,
) -> UUID:
    if isinstance(
        value,
        UUID,
    ):
        return value

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} must be a UUID "
            "or UUID string."
        )

    try:
        return UUID(
            value.strip()
        )
    except ValueError as error:
        raise ValueError(
            f"{field_name} is not a valid UUID."
        ) from error


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


def _parse_example_ids(
    value: object,
    *,
    field_name: str,
) -> tuple[
    UUID,
    ...,
]:
    if not isinstance(
        value,
        list,
    ):
        raise ValueError(
            f"{field_name} must be a list."
        )

    ids: list[
        UUID
    ] = []

    seen: set[
        UUID
    ] = set()

    for item in value:
        example_id = _require_uuid(
            str(
                item
            ),
            field_name=field_name,
        )

        if example_id in seen:
            raise ValueError(
                f"{field_name} contains "
                "duplicate example IDs."
            )

        seen.add(
            example_id
        )

        ids.append(
            example_id
        )

    return tuple(
        ids
    )


class ModelTrainingDatasetMaterializer:
    """
    Materialize an authoritative Data Engine dataset into
    derived train/evaluation JSONL files and a manifest.

    The Data Engine remains the source of truth.

    Materialization does not:
    - create TrainingCandidates;
    - approve candidates;
    - alter eligibility;
    - alter the dataset;
    - train a model.
    """

    def __init__(
        self,
        *,
        data_engine: (
            ModelDevelopmentDataEngine
            | None
        ) = None,
        output_root: (
            str
            | Path
        ) = DEFAULT_DATASET_OUTPUT_ROOT,
    ) -> None:
        self.data_engine = (
            data_engine
            if data_engine is not None
            else ModelDevelopmentDataEngine()
        )

        self.output_root = Path(
            output_root
        )

    def _dataset_record(
        self,
        dataset_id: UUID,
    ) -> dict[str, Any]:
        record = (
            self.data_engine
            .find_model_value(
                data_type=(
                    MODEL_TRAINING_DATASET_DATA_TYPE
                ),
                field_name="id",
                field_value=str(
                    dataset_id
                ),
            )
        )

        if record is None:
            raise ValueError(
                "ModelTrainingDataset was not found: "
                f"{dataset_id}"
            )

        value = _require_dictionary(
            record.get(
                "value"
            ),
            field_name=(
                "ModelTrainingDataset value"
            ),
        )

        if (
            value.get(
                "id"
            )
            != str(
                dataset_id
            )
        ):
            raise ValueError(
                "Dataset UUID does not match "
                "the requested dataset."
            )

        if (
            value.get(
                "status"
            )
            != "ready"
        ):
            raise ValueError(
                "Only ready datasets may "
                "be materialized."
            )

        return record

    def _example_map(
        self,
        *,
        dataset_id: UUID,
    ) -> dict[
        UUID,
        dict[str, Any],
    ]:
        result: dict[
            UUID,
            dict[str, Any],
        ] = {}

        records = (
            self.data_engine
            .records(
                data_type=(
                    MODEL_TRAINING_EXAMPLE_DATA_TYPE
                )
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
                    "dataset_id"
                )
                != str(
                    dataset_id
                )
            ):
                continue

            example_id = _require_uuid(
                str(
                    value.get(
                        "id"
                    )
                ),
                field_name=(
                    "ModelTrainingExample id"
                ),
            )

            if example_id in result:
                raise ValueError(
                    "Duplicate ModelTrainingExample "
                    "UUID exists in the Data Engine."
                )

            result[
                example_id
            ] = record

        return result

    @staticmethod
    def _materialized_example(
        *,
        record: dict[str, Any],
        dataset_id: UUID,
        expected_split: str,
    ) -> dict[str, Any]:
        value = _require_dictionary(
            record.get(
                "value"
            ),
            field_name=(
                "ModelTrainingExample value"
            ),
        )

        if (
            value.get(
                "dataset_id"
            )
            != str(
                dataset_id
            )
        ):
            raise ValueError(
                "Training example references "
                "the wrong dataset."
            )

        if (
            value.get(
                "split"
            )
            != expected_split
        ):
            raise ValueError(
                "Training example split does not "
                "match dataset membership."
            )

        example_id = _require_nonempty_text(
            value.get(
                "id"
            ),
            field_name="example id",
        )

        candidate_record_id = (
            _require_positive_integer(
                value.get(
                    "candidate_record_id"
                ),
                field_name=(
                    "candidate_record_id"
                ),
            )
        )

        source_record_id = (
            _require_positive_integer(
                value.get(
                    "source_record_id"
                ),
                field_name=(
                    "source_record_id"
                ),
            )
        )

        validation_record_id = (
            _require_positive_integer(
                value.get(
                    "training_validation_record_id"
                ),
                field_name=(
                    "training_validation_record_id"
                ),
            )
        )

        source = _require_nonempty_text(
            value.get(
                "source"
            ),
            field_name="source",
        )

        data_type = _require_nonempty_text(
            value.get(
                "data_type"
            ),
            field_name="data_type",
        )

        input_text = _require_nonempty_text(
            value.get(
                "input_text"
            ),
            field_name="input_text",
        )

        target_text = _require_nonempty_text(
            value.get(
                "target_text"
            ),
            field_name="target_text",
        )

        content_hash = (
            _require_nonempty_text(
                value.get(
                    "content_hash"
                ),
                field_name=(
                    "content_hash"
                ),
            )
        )

        evidence_ids = value.get(
            "evidence_ids"
        )

        validation_record_ids = value.get(
            "validation_record_ids"
        )

        if not isinstance(
            evidence_ids,
            list,
        ):
            raise ValueError(
                "evidence_ids must be a list."
            )

        if not isinstance(
            validation_record_ids,
            list,
        ):
            raise ValueError(
                "validation_record_ids "
                "must be a list."
            )

        return {
            "example_id": (
                example_id
            ),
            "dataset_id": str(
                dataset_id
            ),
            "candidate_record_id": (
                candidate_record_id
            ),
            "source_record_id": (
                source_record_id
            ),
            "training_validation_record_id": (
                validation_record_id
            ),
            "source": source,
            "data_type": data_type,
            "input_text": input_text,
            "target_text": target_text,
            "split": expected_split,
            "evidence_ids": list(
                evidence_ids
            ),
            "validation_record_ids": list(
                validation_record_ids
            ),
            "content_hash": (
                content_hash
            ),
        }

    @staticmethod
    def _jsonl_bytes(
        rows: list[
            dict[str, Any]
        ],
    ) -> bytes:
        lines = [
            json.dumps(
                row,
                sort_keys=True,
                ensure_ascii=False,
                separators=(
                    ",",
                    ":",
                ),
            )
            for row in rows
        ]

        return (
            "\n".join(
                lines
            )
            + "\n"
        ).encode(
            "utf-8"
        )

    @staticmethod
    def _write_file(
        path: Path,
        content: bytes,
    ) -> None:
        with open(
            path,
            "wb",
        ) as file:
            file.write(
                content
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

    def materialize(
        self,
        dataset_id: UUID | str,
    ) -> MaterializedDataset:
        normalized_dataset_id = (
            _require_uuid(
                dataset_id,
                field_name=(
                    "dataset_id"
                ),
            )
        )

        dataset_record = (
            self._dataset_record(
                normalized_dataset_id
            )
        )

        dataset = _require_dictionary(
            dataset_record.get(
                "value"
            ),
            field_name=(
                "ModelTrainingDataset value"
            ),
        )

        train_ids = _parse_example_ids(
            dataset.get(
                "training_example_ids"
            ),
            field_name=(
                "training_example_ids"
            ),
        )

        evaluation_ids = (
            _parse_example_ids(
                dataset.get(
                    "evaluation_example_ids"
                ),
                field_name=(
                    "evaluation_example_ids"
                ),
            )
        )

        if not train_ids:
            raise ValueError(
                "Dataset has no training examples."
            )

        if not evaluation_ids:
            raise ValueError(
                "Dataset has no evaluation examples."
            )

        overlap = (
            set(
                train_ids
            )
            &
            set(
                evaluation_ids
            )
        )

        if overlap:
            raise ValueError(
                "Training and evaluation example "
                "IDs overlap."
            )

        declared_training_count = (
            _require_positive_integer(
                dataset.get(
                    "training_examples"
                ),
                field_name=(
                    "training_examples"
                ),
            )
        )

        declared_evaluation_count = (
            _require_positive_integer(
                dataset.get(
                    "evaluation_examples"
                ),
                field_name=(
                    "evaluation_examples"
                ),
            )
        )

        if (
            declared_training_count
            != len(
                train_ids
            )
        ):
            raise ValueError(
                "Dataset training example count "
                "does not match its example IDs."
            )

        if (
            declared_evaluation_count
            != len(
                evaluation_ids
            )
        ):
            raise ValueError(
                "Dataset evaluation example count "
                "does not match its example IDs."
            )

        examples = self._example_map(
            dataset_id=(
                normalized_dataset_id
            )
        )

        expected_ids = (
            set(
                train_ids
            )
            |
            set(
                evaluation_ids
            )
        )

        actual_ids = set(
            examples
        )

        if actual_ids != expected_ids:
            missing = sorted(
                str(
                    item
                )
                for item
                in (
                    expected_ids
                    - actual_ids
                )
            )

            unexpected = sorted(
                str(
                    item
                )
                for item
                in (
                    actual_ids
                    - expected_ids
                )
            )

            raise ValueError(
                "Dataset example membership "
                "does not match Data Engine records. "
                f"missing={missing} "
                f"unexpected={unexpected}"
            )

        train_rows = [
            self._materialized_example(
                record=examples[
                    example_id
                ],
                dataset_id=(
                    normalized_dataset_id
                ),
                expected_split="train",
            )
            for example_id
            in train_ids
        ]

        evaluation_rows = [
            self._materialized_example(
                record=examples[
                    example_id
                ],
                dataset_id=(
                    normalized_dataset_id
                ),
                expected_split="evaluation",
            )
            for example_id
            in evaluation_ids
        ]

        train_content = (
            self._jsonl_bytes(
                train_rows
            )
        )

        evaluation_content = (
            self._jsonl_bytes(
                evaluation_rows
            )
        )

        train_sha256 = _sha256_bytes(
            train_content
        )

        evaluation_sha256 = (
            _sha256_bytes(
                evaluation_content
            )
        )

        manifest = {
            "dataset_record_id": (
                dataset_record.get(
                    "id"
                )
            ),
            "dataset_id": str(
                normalized_dataset_id
            ),
            "name": dataset.get(
                "name"
            ),
            "version": dataset.get(
                "version"
            ),
            "status": dataset.get(
                "status"
            ),
            "selection_policy_version": (
                dataset.get(
                    "selection_policy_version"
                )
            ),
            "split_seed": dataset.get(
                "split_seed"
            ),
            "evaluation_ratio": (
                dataset.get(
                    "evaluation_ratio"
                )
            ),
            "dataset_content_hash": (
                dataset.get(
                    "content_hash"
                )
            ),
            "candidate_record_ids": (
                dataset.get(
                    "candidate_record_ids"
                )
            ),
            "source_record_ids": (
                dataset.get(
                    "source_record_ids"
                )
            ),
            "training_example_ids": [
                str(
                    item
                )
                for item
                in train_ids
            ],
            "evaluation_example_ids": [
                str(
                    item
                )
                for item
                in evaluation_ids
            ],
            "training_examples": len(
                train_rows
            ),
            "evaluation_examples": len(
                evaluation_rows
            ),
            "files": {
                "train.jsonl": {
                    "sha256": (
                        train_sha256
                    ),
                    "records": len(
                        train_rows
                    ),
                },
                "evaluation.jsonl": {
                    "sha256": (
                        evaluation_sha256
                    ),
                    "records": len(
                        evaluation_rows
                    ),
                },
            },
            "authoritative_source": (
                "data_engine"
            ),
        }

        manifest_content = (
            json.dumps(
                manifest,
                sort_keys=True,
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode(
            "utf-8"
        )

        manifest_sha256 = (
            _sha256_bytes(
                manifest_content
            )
        )

        self.output_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        target_directory = (
            self.output_root
            / str(
                normalized_dataset_id
            )
        )

        staging_directory = (
            self.output_root
            / (
                ".materialize-"
                f"{normalized_dataset_id}-"
                f"{uuid4().hex}"
            )
        )

        backup_directory = (
            self.output_root
            / (
                ".previous-"
                f"{normalized_dataset_id}-"
                f"{uuid4().hex}"
            )
        )

        staging_directory.mkdir(
            parents=False,
            exist_ok=False,
        )

        try:
            self._write_file(
                staging_directory
                / "train.jsonl",
                train_content,
            )

            self._write_file(
                staging_directory
                / "evaluation.jsonl",
                evaluation_content,
            )

            self._write_file(
                staging_directory
                / "manifest.json",
                manifest_content,
            )

            if (
                target_directory.exists()
                and not target_directory.is_dir()
            ):
                raise ValueError(
                    "Dataset materialization target "
                    "exists but is not a directory."
                )

            had_previous = (
                target_directory.exists()
            )

            if had_previous:
                os.replace(
                    target_directory,
                    backup_directory,
                )

            try:
                os.replace(
                    staging_directory,
                    target_directory,
                )

            except Exception:
                if (
                    had_previous
                    and backup_directory.exists()
                ):
                    os.replace(
                        backup_directory,
                        target_directory,
                    )

                raise

            if backup_directory.exists():
                shutil.rmtree(
                    backup_directory
                )

        finally:
            if staging_directory.exists():
                shutil.rmtree(
                    staging_directory
                )

        return MaterializedDataset(
            dataset_id=(
                normalized_dataset_id
            ),
            directory=(
                target_directory
            ),
            train_path=(
                target_directory
                / "train.jsonl"
            ),
            evaluation_path=(
                target_directory
                / "evaluation.jsonl"
            ),
            manifest_path=(
                target_directory
                / "manifest.json"
            ),
            train_sha256=(
                train_sha256
            ),
            evaluation_sha256=(
                evaluation_sha256
            ),
            manifest_sha256=(
                manifest_sha256
            ),
            training_examples=len(
                train_rows
            ),
            evaluation_examples=len(
                evaluation_rows
            ),
        )
