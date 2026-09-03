from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_BASE_MODELS_DIRECTORY = Path(
    "data/model_training/bases"
)

DEFAULT_IMAGE_OUTPUT_DIRECTORY = Path(
    "data/model_outputs/images"
)


TEXT_GENERATION = "text_generation"
IMAGE_GENERATION = "image_generation"

TRANSFORMERS_RUNTIME = "transformers"
DIFFUSERS_RUNTIME = "diffusers"


class ModelDevelopmentRuntimeError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True,
    kw_only=True,
)
class BaseModelDescriptor:
    name: str
    path: Path

    model_type: str | None
    architectures: tuple[str, ...]

    capability: str
    runtime_format: str


def _base_directory(
    root: Path | None = None,
) -> Path:
    directory = (
        root
        if root is not None
        else DEFAULT_BASE_MODELS_DIRECTORY
    )

    return directory.resolve()


def _read_json(
    path: Path,
) -> dict[str, Any] | None:
    if not path.is_file():
        return None

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(
        value,
        dict,
    ):
        return None

    return value


def _transformers_descriptor(
    candidate: Path,
    config: dict[str, Any],
) -> BaseModelDescriptor:
    architectures_value = config.get(
        "architectures"
    )

    if not isinstance(
        architectures_value,
        list,
    ):
        architectures_value = []

    architectures = tuple(
        str(value)
        for value
        in architectures_value
    )

    capability = "unknown"

    for architecture in architectures:
        normalized = (
            architecture
            .strip()
            .lower()
        )

        if (
            "causallm" in normalized
            or normalized.endswith(
                "lmheadmodel"
            )
        ):
            capability = (
                TEXT_GENERATION
            )
            break

    model_type = config.get(
        "model_type"
    )

    return BaseModelDescriptor(
        name=candidate.name,
        path=candidate.resolve(),
        model_type=(
            model_type
            if isinstance(
                model_type,
                str,
            )
            else None
        ),
        architectures=architectures,
        capability=capability,
        runtime_format=(
            TRANSFORMERS_RUNTIME
        ),
    )


def _diffusers_descriptor(
    candidate: Path,
    model_index: dict[str, Any],
) -> BaseModelDescriptor:
    pipeline_class = model_index.get(
        "_class_name"
    )

    if not isinstance(
        pipeline_class,
        str,
    ):
        pipeline_class = None

    return BaseModelDescriptor(
        name=candidate.name,
        path=candidate.resolve(),
        model_type=pipeline_class,
        architectures=(
            (pipeline_class,)
            if pipeline_class
            else ()
        ),
        capability=IMAGE_GENERATION,
        runtime_format=(
            DIFFUSERS_RUNTIME
        ),
    )


def discover_base_models(
    root: Path | None = None,
) -> tuple[
    BaseModelDescriptor,
    ...,
]:
    directory = _base_directory(
        root
    )

    if not directory.is_dir():
        return ()

    descriptors: list[
        BaseModelDescriptor
    ] = []

    for candidate in sorted(
        directory.iterdir()
    ):
        if not candidate.is_dir():
            continue

        model_index = _read_json(
            candidate
            / "model_index.json"
        )

        if model_index is not None:
            descriptors.append(
                _diffusers_descriptor(
                    candidate,
                    model_index,
                )
            )
            continue

        config = _read_json(
            candidate
            / "config.json"
        )

        if config is None:
            continue

        descriptors.append(
            _transformers_descriptor(
                candidate,
                config,
            )
        )

    return tuple(
        descriptors
    )


def resolve_base_model(
    model_name: str,
    root: Path | None = None,
) -> BaseModelDescriptor:
    clean_name = str(
        model_name
    ).strip()

    if not clean_name:
        raise ValueError(
            "model_name must not be empty."
        )

    for descriptor in (
        discover_base_models(
            root
        )
    ):
        if (
            descriptor.name
            == clean_name
        ):
            return descriptor

    raise ModelDevelopmentRuntimeError(
        "Local base model not found: "
        f"{clean_name}"
    )


def inspect_base_model(
    model_name: str,
) -> dict[str, Any]:
    descriptor = (
        resolve_base_model(
            model_name
        )
    )

    return {
        "model_name": descriptor.name,
        "model_path": str(
            descriptor.path
        ),
        "model_type": (
            descriptor.model_type
        ),
        "architectures": list(
            descriptor.architectures
        ),
        "capability": (
            descriptor.capability
        ),
        "runtime_format": (
            descriptor.runtime_format
        ),
        "training_performed": False,
        "weights_modified": False,
    }


def _validate_prompt(
    prompt: str,
) -> str:
    clean_prompt = str(
        prompt
    ).strip()

    if not clean_prompt:
        raise ValueError(
            "prompt must not be empty."
        )

    return clean_prompt


def _execute_text_model(
    descriptor: BaseModelDescriptor,
    prompt: str,
    *,
    max_new_tokens: int,
) -> dict[str, Any]:
    try:
        import torch

        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
        )
    except ImportError as error:
        raise ModelDevelopmentRuntimeError(
            "Text generation dependencies "
            "are unavailable."
        ) from error

    started_at = time.monotonic()

    tokenizer = (
        AutoTokenizer
        .from_pretrained(
            descriptor.path,
            local_files_only=True,
        )
    )

    model = (
        AutoModelForCausalLM
        .from_pretrained(
            descriptor.path,
            local_files_only=True,
            dtype=torch.float32,
        )
    )

    model.eval()

    if (
        tokenizer.pad_token_id
        is None
        and tokenizer.eos_token_id
        is not None
    ):
        tokenizer.pad_token = (
            tokenizer.eos_token
        )

    encoded = tokenizer(
        prompt,
        return_tensors="pt",
    )

    input_token_count = int(
        encoded["input_ids"]
        .shape[1]
    )

    with torch.no_grad():
        generated = model.generate(
            **encoded,
            max_new_tokens=(
                max_new_tokens
            ),
            do_sample=False,
            pad_token_id=(
                tokenizer.pad_token_id
                if tokenizer.pad_token_id
                is not None
                else tokenizer.eos_token_id
            ),
        )

    generated_tokens = generated[
        0,
        input_token_count:,
    ]

    generated_text = (
        tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
        )
        .strip()
    )

    return {
        "model_name": descriptor.name,
        "capability": (
            descriptor.capability
        ),
        "runtime_format": (
            descriptor.runtime_format
        ),
        "output_type": "text",
        "generated_text": (
            generated_text
        ),
        "elapsed_seconds": round(
            time.monotonic()
            - started_at,
            2,
        ),
        "model_loaded": True,
        "training_performed": False,
        "weights_modified": False,
    }


def _validate_dimension(
    value: int,
    name: str,
) -> int:
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
        or value < 64
        or value > 1024
        or value % 8 != 0
    ):
        raise ValueError(
            f"{name} must be between "
            "64 and 1024 and divisible "
            "by 8."
        )

    return value


def _execute_image_model(
    descriptor: BaseModelDescriptor,
    prompt: str,
    *,
    output_path: str | Path | None,
    inference_steps: int,
    width: int,
    height: int,
    seed: int,
) -> dict[str, Any]:
    width = _validate_dimension(
        width,
        "width",
    )

    height = _validate_dimension(
        height,
        "height",
    )

    try:
        import torch

        import diffusers

        from diffusers import (
            DiffusionPipeline,
        )
    except ImportError as error:
        raise ModelDevelopmentRuntimeError(
            "Image generation dependencies "
            "are unavailable."
        ) from error

    if output_path is None:
        destination = (
            DEFAULT_IMAGE_OUTPUT_DIRECTORY
            / descriptor.name
            / f"{uuid4()}.png"
        )
    else:
        destination = Path(
            output_path
        )

    destination = (
        destination.resolve()
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_index = (
        _read_json(
            descriptor.path
            / "model_index.json"
        )
        or {}
    )

    load_arguments: dict[
        str,
        Any,
    ] = {
        "local_files_only": True,
        "dtype": torch.float32,
    }

    safety_directory = (
        descriptor.path
        / "safety_checker"
    )

    safety_weight_files = ()

    if safety_directory.is_dir():
        safety_weight_files = tuple(
            file_path
            for pattern in (
                "*.safetensors",
                "*.bin",
            )
            for file_path
            in safety_directory.glob(
                pattern
            )
            if file_path.is_file()
        )

    if (
        "safety_checker"
        in model_index
        and not safety_weight_files
    ):
        load_arguments[
            "safety_checker"
        ] = None

        load_arguments[
            "requires_safety_checker"
        ] = False

    started_at = time.monotonic()

    pipeline_class_name = str(
        model_index.get(
            "_class_name",
            "",
        )
    ).strip()

    if not pipeline_class_name:
        raise ModelDevelopmentRuntimeError(
            "The Diffusers model does not "
            "declare a pipeline class."
        )

    pipeline_class = getattr(
        diffusers,
        pipeline_class_name,
        None,
    )

    if (
        not isinstance(
            pipeline_class,
            type,
        )
        or not issubclass(
            pipeline_class,
            DiffusionPipeline,
        )
    ):
        raise ModelDevelopmentRuntimeError(
            "The declared Diffusers pipeline "
            "class is unavailable: "
            f"{pipeline_class_name}"
        )

    pipeline = (
        pipeline_class
        .from_pretrained(
            descriptor.path,
            **load_arguments,
        )
    )

    pipeline = pipeline.to(
        "cpu"
    )

    attention_slicing = getattr(
        pipeline,
        "enable_attention_slicing",
        None,
    )

    if callable(
        attention_slicing
    ):
        attention_slicing()

    progress_config = getattr(
        pipeline,
        "set_progress_bar_config",
        None,
    )

    if callable(
        progress_config
    ):
        progress_config(
            disable=True
        )

    generator = (
        torch.Generator(
            device="cpu"
        )
        .manual_seed(
            seed
        )
    )

    with torch.inference_mode():
        result = pipeline(
            prompt=prompt,
            num_inference_steps=(
                inference_steps
            ),
            width=width,
            height=height,
            generator=generator,
        )

    images = getattr(
        result,
        "images",
        None,
    )

    if (
        not isinstance(
            images,
            list,
        )
        or not images
    ):
        raise ModelDevelopmentRuntimeError(
            "The image model returned "
            "no image."
        )

    images[0].save(
        destination,
        format="PNG",
    )

    return {
        "model_name": descriptor.name,
        "capability": (
            descriptor.capability
        ),
        "runtime_format": (
            descriptor.runtime_format
        ),
        "output_type": "image",
        "mime_type": "image/png",
        "output_path": str(
            destination
        ),
        "width": width,
        "height": height,
        "inference_steps": (
            inference_steps
        ),
        "seed": seed,
        "elapsed_seconds": round(
            time.monotonic()
            - started_at,
            2,
        ),
        "image_generated": (
            destination.is_file()
        ),
        "model_loaded": True,
        "training_performed": False,
        "weights_modified": False,
    }


def test_base_model(
    model_name: str,
    prompt: str,
    *,
    max_new_tokens: int = 64,
    output_path: (
        str
        | Path
        | None
    ) = None,
    inference_steps: int = 6,
    width: int = 384,
    height: int = 384,
    seed: int = 17,
) -> dict[str, Any]:
    prompt = _validate_prompt(
        prompt
    )

    descriptor = (
        resolve_base_model(
            model_name
        )
    )

    if (
        descriptor.capability
        == TEXT_GENERATION
    ):
        return _execute_text_model(
            descriptor,
            prompt,
            max_new_tokens=(
                max_new_tokens
            ),
        )

    if (
        descriptor.capability
        == IMAGE_GENERATION
    ):
        return _execute_image_model(
            descriptor,
            prompt,
            output_path=output_path,
            inference_steps=(
                inference_steps
            ),
            width=width,
            height=height,
            seed=seed,
        )

    raise ModelDevelopmentRuntimeError(
        "No runtime is registered "
        "for capability: "
        f"{descriptor.capability}"
    )
