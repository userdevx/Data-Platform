from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import random
import shutil
from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any
from uuid import (
    UUID,
    uuid4,
)

import torch
from peft import (
    LoraConfig,
    TaskType,
    get_peft_model,
)
from torch.utils.data import (
    DataLoader,
    Dataset,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)

from engine.model_development.materialize import (
    MaterializedDataset,
)


DEFAULT_CANDIDATE_OUTPUT_ROOT = Path(
    "data/model_training/candidates"
)

DEFAULT_TARGET_MODULES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
)


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


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


def _require_positive_float(
    value: object,
    *,
    field_name: str,
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
            f"{field_name} must be numeric."
        )

    normalized = float(
        value
    )

    if normalized <= 0.0:
        raise ValueError(
            f"{field_name} must be greater than zero."
        )

    return normalized


def _require_probability(
    value: object,
    *,
    field_name: str,
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
            f"{field_name} must be numeric."
        )

    normalized = float(
        value
    )

    if not (
        0.0
        <= normalized
        < 1.0
    ):
        raise ValueError(
            f"{field_name} must be greater than "
            "or equal to 0 and less than 1."
        )

    return normalized


def _require_path(
    value: str | Path,
    *,
    field_name: str,
) -> Path:
    if not isinstance(
        value,
        (
            str,
            Path,
        ),
    ):
        raise TypeError(
            f"{field_name} must be a path."
        )

    path = Path(
        value
    )

    if not str(
        path
    ).strip():
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return path


def _normalize_target_modules(
    values: tuple[
        str,
        ...,
    ],
) -> tuple[
    str,
    ...,
]:
    if not isinstance(
        values,
        tuple,
    ):
        raise TypeError(
            "target_modules must be a tuple."
        )

    if not values:
        raise ValueError(
            "At least one LoRA target module "
            "is required."
        )

    result: list[
        str
    ] = []

    seen: set[
        str
    ] = set()

    for value in values:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "Every LoRA target module "
                "must be a string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "LoRA target modules must "
                "not be empty."
            )

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        result.append(
            normalized
        )

    return tuple(
        result
    )


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with open(
        path,
        "rb",
    ) as file:
        while True:
            block = file.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _read_jsonl(
    path: Path,
    *,
    expected_split: str,
) -> list[
    dict[str, Any]
]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Materialized dataset file "
            f"does not exist: {path}"
        )

    rows: list[
        dict[str, Any]
    ] = []

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                row = json.loads(
                    stripped
                )
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Invalid JSONL row in "
                    f"{path} at line "
                    f"{line_number}."
                ) from error

            if not isinstance(
                row,
                dict,
            ):
                raise ValueError(
                    "Every materialized dataset "
                    "row must be an object."
                )

            split = row.get(
                "split"
            )

            if split != expected_split:
                raise ValueError(
                    "Materialized dataset split "
                    "does not match its file."
                )

            input_text = row.get(
                "input_text"
            )

            target_text = row.get(
                "target_text"
            )

            if (
                not isinstance(
                    input_text,
                    str,
                )
                or not input_text.strip()
            ):
                raise ValueError(
                    "Training input_text must "
                    "be a non-empty string."
                )

            if (
                not isinstance(
                    target_text,
                    str,
                )
                or not target_text.strip()
            ):
                raise ValueError(
                    "Training target_text must "
                    "be a non-empty string."
                )

            rows.append(
                row
            )

    if not rows:
        raise ValueError(
            f"Materialized {expected_split} "
            "dataset is empty."
        )

    return rows


@dataclass(
    frozen=True,
    kw_only=True,
)
class LoRATrainingConfiguration:
    base_model_path: Path

    output_root: Path = (
        DEFAULT_CANDIDATE_OUTPUT_ROOT
    )

    target_modules: tuple[
        str,
        ...,
    ] = DEFAULT_TARGET_MODULES

    rank: int = 8

    alpha: int = 16

    dropout: float = 0.05

    max_sequence_length: int = 256

    epochs: int = 1

    batch_size: int = 1

    gradient_accumulation_steps: int = 1

    learning_rate: float = 2.0e-4

    weight_decay: float = 0.0

    seed: int = 17

    max_optimizer_steps: int | None = None

    device: str = "auto"

    def __post_init__(
        self,
    ) -> None:
        base_model_path = _require_path(
            self.base_model_path,
            field_name="base_model_path",
        ).resolve()

        output_root = _require_path(
            self.output_root,
            field_name="output_root",
        )

        target_modules = (
            _normalize_target_modules(
                self.target_modules
            )
        )

        _require_positive_integer(
            self.rank,
            field_name="rank",
        )

        _require_positive_integer(
            self.alpha,
            field_name="alpha",
        )

        _require_probability(
            self.dropout,
            field_name="dropout",
        )

        max_sequence_length = (
            _require_positive_integer(
                self.max_sequence_length,
                field_name=(
                    "max_sequence_length"
                ),
            )
        )

        if max_sequence_length < 8:
            raise ValueError(
                "max_sequence_length must be "
                "at least 8."
            )

        _require_positive_integer(
            self.epochs,
            field_name="epochs",
        )

        _require_positive_integer(
            self.batch_size,
            field_name="batch_size",
        )

        _require_positive_integer(
            self.gradient_accumulation_steps,
            field_name=(
                "gradient_accumulation_steps"
            ),
        )

        _require_positive_float(
            self.learning_rate,
            field_name="learning_rate",
        )

        if (
            isinstance(
                self.weight_decay,
                bool,
            )
            or not isinstance(
                self.weight_decay,
                (
                    int,
                    float,
                ),
            )
        ):
            raise TypeError(
                "weight_decay must be numeric."
            )

        if float(
            self.weight_decay
        ) < 0.0:
            raise ValueError(
                "weight_decay must be greater "
                "than or equal to zero."
            )

        if (
            isinstance(
                self.seed,
                bool,
            )
            or not isinstance(
                self.seed,
                int,
            )
        ):
            raise TypeError(
                "seed must be an integer."
            )

        if self.max_optimizer_steps is not None:
            _require_positive_integer(
                self.max_optimizer_steps,
                field_name=(
                    "max_optimizer_steps"
                ),
            )

        if not isinstance(
            self.device,
            str,
        ):
            raise TypeError(
                "device must be a string."
            )

        normalized_device = (
            self.device
            .strip()
            .casefold()
        )

        if normalized_device not in {
            "auto",
            "cpu",
            "cuda",
        }:
            raise ValueError(
                "device must be one of: "
                "auto, cpu, cuda."
            )

        object.__setattr__(
            self,
            "base_model_path",
            base_model_path,
        )

        object.__setattr__(
            self,
            "output_root",
            output_root,
        )

        object.__setattr__(
            self,
            "target_modules",
            target_modules,
        )

        object.__setattr__(
            self,
            "device",
            normalized_device,
        )


@dataclass(
    frozen=True,
    kw_only=True,
)
class LoRAModelInspection:
    base_model_path: Path

    device: str

    target_modules: tuple[
        str,
        ...,
    ]

    trainable_parameters: int

    total_parameters: int

    trainable_percentage: float


@dataclass(
    frozen=True,
    kw_only=True,
)
class LoRATrainingResult:
    candidate_id: UUID

    dataset_id: UUID

    candidate_directory: Path

    training_manifest_path: Path

    adapter_config_path: Path

    adapter_model_path: Path

    train_examples: int

    evaluation_examples: int

    optimizer_steps: int

    train_loss: float

    evaluation_loss: float

    trainable_parameters: int

    total_parameters: int

    started_at: datetime

    completed_at: datetime


class _CausalTrainingDataset(
    Dataset,
):
    def __init__(
        self,
        *,
        rows: list[
            dict[str, Any]
        ],
        tokenizer: Any,
        max_sequence_length: int,
    ) -> None:
        self.rows = rows

        self.tokenizer = tokenizer

        self.max_sequence_length = (
            max_sequence_length
        )

        if (
            self.tokenizer.eos_token_id
            is None
        ):
            raise ValueError(
                "Tokenizer must define an "
                "EOS token."
            )

    def __len__(
        self,
    ) -> int:
        return len(
            self.rows
        )

    def __getitem__(
        self,
        index: int,
    ) -> dict[
        str,
        list[int]
    ]:
        row = self.rows[
            index
        ]

        input_text = str(
            row[
                "input_text"
            ]
        ).strip()

        target_text = str(
            row[
                "target_text"
            ]
        ).strip()

        prompt_ids = (
            self.tokenizer(
                input_text,
                add_special_tokens=True,
                truncation=False,
            )[
                "input_ids"
            ]
        )

        target_ids = (
            self.tokenizer(
                target_text,
                add_special_tokens=False,
                truncation=False,
            )[
                "input_ids"
            ]
        )

        target_ids = list(
            target_ids
        )

        target_ids.append(
            int(
                self.tokenizer
                .eos_token_id
            )
        )

        if not prompt_ids:
            raise ValueError(
                "Tokenizer produced no input "
                "tokens."
            )

        if len(
            target_ids
        ) >= self.max_sequence_length:
            target_ids = target_ids[
                :(
                    self.max_sequence_length
                    - 1
                )
            ]

        prompt_capacity = (
            self.max_sequence_length
            - len(
                target_ids
            )
        )

        if prompt_capacity < 1:
            raise RuntimeError(
                "No token capacity remains "
                "for the training input."
            )

        prompt_ids = list(
            prompt_ids[
                -prompt_capacity:
            ]
        )

        input_ids = (
            prompt_ids
            + target_ids
        )

        labels = (
            [
                -100
                for _ in prompt_ids
            ]
            + target_ids
        )

        attention_mask = [
            1
            for _ in input_ids
        ]

        return {
            "input_ids": input_ids,
            "attention_mask": (
                attention_mask
            ),
            "labels": labels,
        }


class _CausalBatchCollator:
    def __init__(
        self,
        *,
        pad_token_id: int,
    ) -> None:
        self.pad_token_id = (
            int(
                pad_token_id
            )
        )

    def __call__(
        self,
        rows: list[
            dict[
                str,
                list[int],
            ]
        ],
    ) -> dict[
        str,
        torch.Tensor
    ]:
        max_length = max(
            len(
                row[
                    "input_ids"
                ]
            )
            for row in rows
        )

        input_ids: list[
            list[int]
        ] = []

        attention_masks: list[
            list[int]
        ] = []

        labels: list[
            list[int]
        ] = []

        for row in rows:
            padding = (
                max_length
                - len(
                    row[
                        "input_ids"
                    ]
                )
            )

            input_ids.append(
                row[
                    "input_ids"
                ]
                + [
                    self.pad_token_id
                ]
                * padding
            )

            attention_masks.append(
                row[
                    "attention_mask"
                ]
                + [
                    0
                ]
                * padding
            )

            labels.append(
                row[
                    "labels"
                ]
                + [
                    -100
                ]
                * padding
            )

        return {
            "input_ids": torch.tensor(
                input_ids,
                dtype=torch.long,
            ),
            "attention_mask": (
                torch.tensor(
                    attention_masks,
                    dtype=torch.long,
                )
            ),
            "labels": torch.tensor(
                labels,
                dtype=torch.long,
            ),
        }


class LoRATrainer:
    """
    Train a PEFT LoRA adapter against an existing
    materialized Model Development dataset.

    The base model is loaded read-only from its existing
    local directory.

    This runtime does not:
    - create TrainingCandidates;
    - approve training candidates;
    - determine training eligibility;
    - build datasets;
    - alter the Data Engine dataset;
    - overwrite the base model;
    - release or activate a model.

    Successful output is a new candidate adapter directory.
    """

    def __init__(
        self,
        *,
        configuration: LoRATrainingConfiguration,
    ) -> None:
        if not isinstance(
            configuration,
            LoRATrainingConfiguration,
        ):
            raise TypeError(
                "configuration must be a "
                "LoRATrainingConfiguration."
            )

        self.configuration = (
            configuration
        )

    def _device(
        self,
    ) -> torch.device:
        requested = (
            self.configuration.device
        )

        if requested == "cpu":
            return torch.device(
                "cpu"
            )

        if requested == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA was requested but is "
                    "not available."
                )

            return torch.device(
                "cuda"
            )

        if torch.cuda.is_available():
            return torch.device(
                "cuda"
            )

        return torch.device(
            "cpu"
        )

    def _verify_base_model(
        self,
    ) -> None:
        required = (
            "config.json",
            "model.safetensors",
            "tokenizer_config.json",
        )

        if not (
            self.configuration
            .base_model_path
            .is_dir()
        ):
            raise FileNotFoundError(
                "Base model directory does "
                "not exist: "
                f"{self.configuration.base_model_path}"
            )

        for filename in required:
            path = (
                self.configuration
                .base_model_path
                / filename
            )

            if not path.is_file():
                raise FileNotFoundError(
                    "Required base model file "
                    f"is missing: {path}"
                )

    def _load_tokenizer(
        self,
    ) -> Any:
        tokenizer = (
            AutoTokenizer
            .from_pretrained(
                self.configuration
                .base_model_path,
                local_files_only=True,
                use_fast=True,
            )
        )

        if tokenizer.eos_token_id is None:
            raise ValueError(
                "Base tokenizer has no EOS token."
            )

        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = (
                tokenizer.eos_token
            )

        return tokenizer

    def _load_model(
        self,
        *,
        device: torch.device,
    ) -> Any:
        model = (
            AutoModelForCausalLM
            .from_pretrained(
                self.configuration
                .base_model_path,
                local_files_only=True,
                dtype=torch.float32,
            )
        )

        lora_configuration = (
            LoraConfig(
                task_type=(
                    TaskType.CAUSAL_LM
                ),
                inference_mode=False,
                r=(
                    self.configuration.rank
                ),
                lora_alpha=(
                    self.configuration.alpha
                ),
                lora_dropout=(
                    self.configuration.dropout
                ),
                bias="none",
                target_modules=list(
                    self.configuration
                    .target_modules
                ),
            )
        )

        model = get_peft_model(
            model,
            lora_configuration,
        )

        model.config.use_cache = False

        model.to(
            device
        )

        return model

    @staticmethod
    def _parameter_counts(
        model: Any,
    ) -> tuple[
        int,
        int,
    ]:
        total = sum(
            parameter.numel()
            for parameter
            in model.parameters()
        )

        trainable = sum(
            parameter.numel()
            for parameter
            in model.parameters()
            if parameter.requires_grad
        )

        if total < 1:
            raise RuntimeError(
                "Model contains no parameters."
            )

        if trainable < 1:
            raise RuntimeError(
                "LoRA configuration produced "
                "no trainable parameters."
            )

        return (
            trainable,
            total,
        )

    def inspect(
        self,
    ) -> LoRAModelInspection:
        """
        Load the local base model, apply LoRA in memory,
        report trainable parameter counts, then release it.

        No training is performed and no model files are
        written.
        """

        self._verify_base_model()

        device = self._device()

        model = self._load_model(
            device=device
        )

        try:
            (
                trainable,
                total,
            ) = self._parameter_counts(
                model
            )

            return LoRAModelInspection(
                base_model_path=(
                    self.configuration
                    .base_model_path
                ),
                device=str(
                    device
                ),
                target_modules=(
                    self.configuration
                    .target_modules
                ),
                trainable_parameters=(
                    trainable
                ),
                total_parameters=total,
                trainable_percentage=(
                    (
                        trainable
                        / total
                    )
                    * 100.0
                ),
            )

        finally:
            del model

            gc.collect()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    @staticmethod
    def _verify_materialized_dataset(
        dataset: MaterializedDataset,
    ) -> None:
        if not isinstance(
            dataset,
            MaterializedDataset,
        ):
            raise TypeError(
                "dataset must be a "
                "MaterializedDataset."
            )

        checks = (
            (
                dataset.train_path,
                dataset.train_sha256,
                "train",
            ),
            (
                dataset.evaluation_path,
                dataset.evaluation_sha256,
                "evaluation",
            ),
            (
                dataset.manifest_path,
                dataset.manifest_sha256,
                "manifest",
            ),
        )

        for (
            path,
            expected_hash,
            label,
        ) in checks:
            if not path.is_file():
                raise FileNotFoundError(
                    f"Materialized {label} file "
                    f"does not exist: {path}"
                )

            actual_hash = (
                _sha256_file(
                    path
                )
            )

            if actual_hash != expected_hash:
                raise ValueError(
                    "Materialized dataset hash "
                    f"mismatch for {label}."
                )

    @staticmethod
    def _move_batch(
        batch: dict[
            str,
            torch.Tensor,
        ],
        *,
        device: torch.device,
    ) -> dict[
        str,
        torch.Tensor,
    ]:
        return {
            name: tensor.to(
                device
            )
            for name, tensor
            in batch.items()
        }

    @staticmethod
    def _evaluate(
        *,
        model: Any,
        loader: DataLoader,
        device: torch.device,
    ) -> float:
        model.eval()

        losses: list[
            float
        ] = []

        with torch.no_grad():
            for batch in loader:
                moved = (
                    LoRATrainer
                    ._move_batch(
                        batch,
                        device=device,
                    )
                )

                output = model(
                    **moved
                )

                loss = float(
                    output.loss.detach()
                    .cpu()
                    .item()
                )

                if not math.isfinite(
                    loss
                ):
                    raise RuntimeError(
                        "Evaluation produced "
                        "a non-finite loss."
                    )

                losses.append(
                    loss
                )

        if not losses:
            raise RuntimeError(
                "Evaluation loader produced "
                "no batches."
            )

        return sum(
            losses
        ) / len(
            losses
        )

    @staticmethod
    def _candidate_file_hashes(
        directory: Path,
    ) -> dict[
        str,
        str,
    ]:
        hashes: dict[
            str,
            str,
        ] = {}

        for path in sorted(
            directory.rglob(
                "*"
            )
        ):
            if not path.is_file():
                continue

            if (
                path.name
                == "training_manifest.json"
            ):
                continue

            relative = str(
                path.relative_to(
                    directory
                )
            )

            hashes[
                relative
            ] = _sha256_file(
                path
            )

        return hashes

    def train(
        self,
        *,
        dataset: MaterializedDataset,
    ) -> LoRATrainingResult:
        self._verify_base_model()

        self._verify_materialized_dataset(
            dataset
        )

        train_rows = _read_jsonl(
            dataset.train_path,
            expected_split="train",
        )

        evaluation_rows = _read_jsonl(
            dataset.evaluation_path,
            expected_split="evaluation",
        )

        if (
            len(
                train_rows
            )
            != dataset.training_examples
        ):
            raise ValueError(
                "Materialized training example "
                "count does not match its contract."
            )

        if (
            len(
                evaluation_rows
            )
            != dataset.evaluation_examples
        ):
            raise ValueError(
                "Materialized evaluation example "
                "count does not match its contract."
            )

        random.seed(
            self.configuration.seed
        )

        torch.manual_seed(
            self.configuration.seed
        )

        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(
                self.configuration.seed
            )

        device = self._device()

        tokenizer = (
            self._load_tokenizer()
        )

        train_dataset = (
            _CausalTrainingDataset(
                rows=train_rows,
                tokenizer=tokenizer,
                max_sequence_length=(
                    self.configuration
                    .max_sequence_length
                ),
            )
        )

        evaluation_dataset = (
            _CausalTrainingDataset(
                rows=evaluation_rows,
                tokenizer=tokenizer,
                max_sequence_length=(
                    self.configuration
                    .max_sequence_length
                ),
            )
        )

        collator = _CausalBatchCollator(
            pad_token_id=(
                tokenizer.pad_token_id
            )
        )

        generator = torch.Generator()

        generator.manual_seed(
            self.configuration.seed
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=(
                self.configuration
                .batch_size
            ),
            shuffle=True,
            collate_fn=collator,
            num_workers=0,
            generator=generator,
        )

        evaluation_loader = DataLoader(
            evaluation_dataset,
            batch_size=(
                self.configuration
                .batch_size
            ),
            shuffle=False,
            collate_fn=collator,
            num_workers=0,
        )

        model = self._load_model(
            device=device
        )

        (
            trainable_parameters,
            total_parameters,
        ) = self._parameter_counts(
            model
        )

        optimizer = torch.optim.AdamW(
            (
                parameter
                for parameter
                in model.parameters()
                if parameter.requires_grad
            ),
            lr=(
                self.configuration
                .learning_rate
            ),
            weight_decay=float(
                self.configuration
                .weight_decay
            ),
        )

        candidate_id = uuid4()

        candidate_root = (
            self.configuration
            .output_root
        )

        candidate_directory = (
            candidate_root
            / str(
                candidate_id
            )
        )

        temporary_directory = (
            candidate_root
            / (
                "."
                + str(
                    candidate_id
                )
                + ".tmp"
            )
        )

        if candidate_directory.exists():
            raise FileExistsError(
                "Model candidate directory "
                "already exists."
            )

        if temporary_directory.exists():
            shutil.rmtree(
                temporary_directory
            )

        candidate_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_directory.mkdir(
            parents=False,
            exist_ok=False,
        )

        started_at = _utc_now()

        train_losses: list[
            float
        ] = []

        optimizer_steps = 0

        stop_requested = False

        optimizer.zero_grad(
            set_to_none=True
        )

        try:
            model.train()

            for _epoch in range(
                self.configuration.epochs
            ):
                for (
                    batch_index,
                    batch,
                ) in enumerate(
                    train_loader,
                    start=1,
                ):
                    moved = self._move_batch(
                        batch,
                        device=device,
                    )

                    output = model(
                        **moved
                    )

                    raw_loss = (
                        output.loss
                    )

                    raw_loss_value = float(
                        raw_loss.detach()
                        .cpu()
                        .item()
                    )

                    if not math.isfinite(
                        raw_loss_value
                    ):
                        raise RuntimeError(
                            "Training produced "
                            "a non-finite loss."
                        )

                    train_losses.append(
                        raw_loss_value
                    )

                    scaled_loss = (
                        raw_loss
                        / self.configuration
                        .gradient_accumulation_steps
                    )

                    scaled_loss.backward()

                    accumulation_boundary = (
                        (
                            batch_index
                            % self.configuration
                            .gradient_accumulation_steps
                        )
                        == 0
                    )

                    final_batch = (
                        batch_index
                        == len(
                            train_loader
                        )
                    )

                    if (
                        accumulation_boundary
                        or final_batch
                    ):
                        optimizer.step()

                        optimizer.zero_grad(
                            set_to_none=True
                        )

                        optimizer_steps += 1

                        max_steps = (
                            self.configuration
                            .max_optimizer_steps
                        )

                        if (
                            max_steps is not None
                            and optimizer_steps
                            >= max_steps
                        ):
                            stop_requested = True
                            break

                if stop_requested:
                    break

            if optimizer_steps < 1:
                raise RuntimeError(
                    "Training completed without "
                    "an optimizer step."
                )

            if not train_losses:
                raise RuntimeError(
                    "Training completed without "
                    "a recorded loss."
                )

            train_loss = (
                sum(
                    train_losses
                )
                / len(
                    train_losses
                )
            )

            evaluation_loss = (
                self._evaluate(
                    model=model,
                    loader=evaluation_loader,
                    device=device,
                )
            )

            model.save_pretrained(
                temporary_directory,
                safe_serialization=True,
            )

            tokenizer.save_pretrained(
                temporary_directory
            )

            adapter_config_path = (
                temporary_directory
                / "adapter_config.json"
            )

            adapter_model_path = (
                temporary_directory
                / "adapter_model.safetensors"
            )

            if not adapter_config_path.is_file():
                raise RuntimeError(
                    "LoRA adapter configuration "
                    "was not saved."
                )

            if not adapter_model_path.is_file():
                raise RuntimeError(
                    "LoRA adapter weights "
                    "were not saved."
                )

            completed_at = _utc_now()

            candidate_hashes = (
                self._candidate_file_hashes(
                    temporary_directory
                )
            )

            manifest = {
                "candidate_id": str(
                    candidate_id
                ),
                "dataset": {
                    "dataset_id": str(
                        dataset.dataset_id
                    ),
                    "train_sha256": (
                        dataset.train_sha256
                    ),
                    "evaluation_sha256": (
                        dataset.evaluation_sha256
                    ),
                    "manifest_sha256": (
                        dataset.manifest_sha256
                    ),
                    "training_examples": (
                        dataset.training_examples
                    ),
                    "evaluation_examples": (
                        dataset.evaluation_examples
                    ),
                },
                "base_model": {
                    "path": str(
                        self.configuration
                        .base_model_path
                    ),
                    "local_files_only": True,
                    "base_model_modified": False,
                },
                "training": {
                    "method": "lora",
                    "task_type": (
                        "causal_language_modeling"
                    ),
                    "rank": (
                        self.configuration.rank
                    ),
                    "alpha": (
                        self.configuration.alpha
                    ),
                    "dropout": (
                        self.configuration.dropout
                    ),
                    "target_modules": list(
                        self.configuration
                        .target_modules
                    ),
                    "max_sequence_length": (
                        self.configuration
                        .max_sequence_length
                    ),
                    "epochs": (
                        self.configuration.epochs
                    ),
                    "batch_size": (
                        self.configuration
                        .batch_size
                    ),
                    "gradient_accumulation_steps": (
                        self.configuration
                        .gradient_accumulation_steps
                    ),
                    "learning_rate": (
                        self.configuration
                        .learning_rate
                    ),
                    "weight_decay": (
                        self.configuration
                        .weight_decay
                    ),
                    "seed": (
                        self.configuration.seed
                    ),
                    "device": str(
                        device
                    ),
                    "optimizer_steps": (
                        optimizer_steps
                    ),
                    "train_loss": (
                        train_loss
                    ),
                    "evaluation_loss": (
                        evaluation_loss
                    ),
                },
                "parameters": {
                    "trainable": (
                        trainable_parameters
                    ),
                    "total": (
                        total_parameters
                    ),
                    "trainable_percentage": (
                        (
                            trainable_parameters
                            / total_parameters
                        )
                        * 100.0
                    ),
                },
                "artifacts": (
                    candidate_hashes
                ),
                "started_at": (
                    started_at.isoformat()
                ),
                "completed_at": (
                    completed_at.isoformat()
                ),
            }

            training_manifest_path = (
                temporary_directory
                / "training_manifest.json"
            )

            with open(
                training_manifest_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    manifest,
                    file,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )

                file.write(
                    "\n"
                )

                file.flush()

                os.fsync(
                    file.fileno()
                )

            os.replace(
                temporary_directory,
                candidate_directory,
            )

            return LoRATrainingResult(
                candidate_id=(
                    candidate_id
                ),
                dataset_id=(
                    dataset.dataset_id
                ),
                candidate_directory=(
                    candidate_directory
                ),
                training_manifest_path=(
                    candidate_directory
                    / "training_manifest.json"
                ),
                adapter_config_path=(
                    candidate_directory
                    / "adapter_config.json"
                ),
                adapter_model_path=(
                    candidate_directory
                    / "adapter_model.safetensors"
                ),
                train_examples=len(
                    train_rows
                ),
                evaluation_examples=len(
                    evaluation_rows
                ),
                optimizer_steps=(
                    optimizer_steps
                ),
                train_loss=(
                    train_loss
                ),
                evaluation_loss=(
                    evaluation_loss
                ),
                trainable_parameters=(
                    trainable_parameters
                ),
                total_parameters=(
                    total_parameters
                ),
                started_at=(
                    started_at
                ),
                completed_at=(
                    completed_at
                ),
            )

        except Exception:
            if temporary_directory.exists():
                shutil.rmtree(
                    temporary_directory
                )

            raise

        finally:
            del optimizer
            del model

            gc.collect()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
