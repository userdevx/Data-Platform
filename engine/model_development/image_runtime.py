from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from uuid import uuid4


WEIGHT_PATTERNS = (
    "*.safetensors",
    "*.bin",
)

MINIMUM_PIXEL_STANDARD_DEVIATION = 2.0


class ImageRuntimeError(
    RuntimeError
):
    pass


def _read_json(
    path: Path,
) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise ImageRuntimeError(
            "The image model index "
            "could not be loaded."
        ) from error

    if not isinstance(
        value,
        dict,
    ):
        raise ImageRuntimeError(
            "The image model index must "
            "contain a JSON object."
        )

    return value


def _module_identity(
    module_name: str,
    required_symbols: tuple[str, ...],
) -> dict[str, Any]:
    module = importlib.import_module(
        module_name
    )

    module_file = getattr(
        module,
        "__file__",
        None,
    )

    if not isinstance(
        module_file,
        str,
    ):
        raise ImageRuntimeError(
            "The runtime module has no "
            "filesystem source path: "
            f"{module_name}"
        )

    source_path = Path(
        module_file
    ).resolve()

    if not source_path.is_file():
        raise ImageRuntimeError(
            "The runtime module source "
            "does not exist: "
            f"{source_path}"
        )

    missing_symbols = [
        symbol
        for symbol in required_symbols
        if not hasattr(
            module,
            symbol,
        )
    ]

    return {
        "module": module_name,
        "resolved_path": str(
            source_path
        ),
        "sha256": hashlib.sha256(
            source_path.read_bytes()
        ).hexdigest(),
        "cached_bytecode": str(
            getattr(
                module,
                "__cached__",
                "",
            )
            or ""
        ),
        "mtime": (
            source_path
            .stat()
            .st_mtime
        ),
        "required_symbols": list(
            required_symbols
        ),
        "missing_symbols": (
            missing_symbols
        ),
        "symbols_resolve": (
            not missing_symbols
        ),
    }


def worker_runtime_identity(
) -> dict[str, Any]:
    return {
        "python_executable": (
            sys.executable
        ),
        "working_directory": (
            os.getcwd()
        ),
        "pythonpath_env": (
            os.environ.get(
                "PYTHONPATH",
                "",
            )
        ),
        "sys_path_head": list(
            sys.path[:5]
        ),
        "runtime": _module_identity(
            (
                "engine."
                "model_development."
                "runtime"
            ),
            (
                "_execute_image_model",
                "test_base_model",
            ),
        ),
        "image_runtime": (
            _module_identity(
                (
                    "engine."
                    "model_development."
                    "image_runtime"
                ),
                (
                    "execute_image_model",
                    "_resolve_pipeline_class",
                    "_validate_generated_image",
                ),
            )
        ),
    }


def _validate_dimension(
    name: str,
    value: int,
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


def _component_has_weights(
    component_path: Path,
) -> bool:
    if not component_path.is_dir():
        return False

    return any(
        candidate.is_file()
        for pattern in WEIGHT_PATTERNS
        for candidate
        in component_path.rglob(
            pattern
        )
    )


def _import_component_module(
    library_name: str,
):
    clean_library_name = (
        library_name.strip()
    )

    if not clean_library_name:
        return None

    candidate_names: list[str] = []

    for candidate in (
        clean_library_name,
        (
            "diffusers.pipelines."
            f"{clean_library_name}"
        ),
        "diffusers",
        "transformers",
    ):
        if (
            candidate
            and candidate
            not in candidate_names
        ):
            candidate_names.append(
                candidate
            )

    for candidate_name in (
        candidate_names
    ):
        try:
            return importlib.import_module(
                candidate_name
            )
        except ImportError:
            continue

    return None

def _component_class(
    model_index: dict[str, Any],
    component_name: str,
) -> type | None:
    specification = model_index.get(
        component_name
    )

    if (
        not isinstance(
            specification,
            (
                list,
                tuple,
            ),
        )
        or len(specification) < 2
    ):
        return None

    library_name = specification[0]
    class_name = specification[1]

    if (
        not isinstance(
            library_name,
            str,
        )
        or not isinstance(
            class_name,
            str,
        )
        or not library_name.strip()
        or not class_name.strip()
    ):
        return None

    clean_library_name = (
        library_name.strip()
    )

    clean_class_name = (
        class_name.strip()
    )

    candidate_module_names: list[
        str
    ] = []

    for module_name in (
        clean_library_name,
        (
            "diffusers.pipelines."
            f"{clean_library_name}"
        ),
        "diffusers",
        "transformers",
    ):
        if (
            module_name
            and module_name
            not in candidate_module_names
        ):
            candidate_module_names.append(
                module_name
            )

    for module_name in (
        candidate_module_names
    ):
        try:
            module = (
                importlib.import_module(
                    module_name
                )
            )
        except ImportError:
            continue

        candidate = getattr(
            module,
            clean_class_name,
            None,
        )

        if isinstance(
            candidate,
            type,
        ):
            return candidate

    return None



def _class_requires_weights(
    component_class: type | None,
) -> bool:
    if component_class is None:
        return False

    weighted_base_classes = {
        "PreTrainedModel",
        "ModelMixin",
    }

    return any(
        base.__name__
        in weighted_base_classes
        for base
        in component_class.__mro__
    )


def _resolve_pipeline_class(
    diffusers_module,
    model_index: dict[str, Any],
) -> dict[str, Any]:
    declared_name = str(
        model_index.get(
            "_class_name",
            "",
        )
    ).strip()

    if declared_name:
        declared_class = getattr(
            diffusers_module,
            declared_name,
            None,
        )

        if callable(
            getattr(
                declared_class,
                "from_pretrained",
                None,
            )
        ):
            return {
                "pipeline_class": (
                    declared_class
                ),
                "pipeline_class_name": (
                    declared_name
                ),
                "resolution": (
                    "declared"
                ),
                "fallback_used": False,
            }

    for fallback_name in (
        "AutoPipelineForText2Image",
        "DiffusionPipeline",
    ):
        fallback_class = getattr(
            diffusers_module,
            fallback_name,
            None,
        )

        if callable(
            getattr(
                fallback_class,
                "from_pretrained",
                None,
            )
        ):
            return {
                "pipeline_class": (
                    fallback_class
                ),
                "pipeline_class_name": (
                    fallback_name
                ),
                "resolution": (
                    "fallback"
                ),
                "fallback_used": True,
                "declared_pipeline_class": (
                    declared_name
                ),
            }

    raise ImageRuntimeError(
        "No compatible image-generation "
        "pipeline class is available."
    )


def _optional_components(
    pipeline_class,
) -> set[str]:
    components = set(
        getattr(
            pipeline_class,
            "_optional_components",
            (),
        )
        or ()
    )

    try:
        signature = inspect.signature(
            pipeline_class.__init__
        )
    except (
        TypeError,
        ValueError,
    ):
        return components

    for name, parameter in (
        signature.parameters.items()
    ):
        if name == "self":
            continue

        if (
            parameter.default
            is inspect.Parameter.empty
        ):
            continue

        components.add(
            name
        )

    return components


def _component_overrides(
    *,
    pipeline_class,
    model_index: dict[str, Any],
    model_path: Path,
) -> dict[str, Any]:
    optional = _optional_components(
        pipeline_class
    )

    overrides: dict[
        str,
        Any,
    ] = {}

    for component_name in optional:
        if (
            component_name
            not in model_index
        ):
            continue

        component_path = (
            model_path
            / component_name
        )

        if not component_path.is_dir():
            overrides[
                component_name
            ] = None

            continue

        has_weights = (
            _component_has_weights(
                component_path
            )
        )

        component_class = (
            _component_class(
                model_index,
                component_name,
            )
        )

        if component_class is None:
            # Optional component whose
            # implementation cannot be resolved:
            # trust the local materialization.
            #
            # If it has no model weights, disable
            # it rather than allowing the pipeline
            # loader to discover the problem later.
            if not has_weights:
                overrides[
                    component_name
                ] = None

            continue

        if (
            _class_requires_weights(
                component_class
            )
            and not has_weights
        ):
            overrides[
                component_name
            ] = None

    if (
        overrides.get(
            "safety_checker",
            object(),
        )
        is None
    ):
        try:
            signature = inspect.signature(
                pipeline_class.__init__
            )
        except (
            TypeError,
            ValueError,
        ):
            signature = None

        if (
            signature is not None
            and (
                "requires_safety_checker"
                in signature.parameters
            )
        ):
            overrides[
                "requires_safety_checker"
            ] = False

    return overrides





def _validate_required_components(
    *,
    pipeline_class,
    model_index: dict[str, Any],
    model_path: Path,
) -> None:
    optional = _optional_components(
        pipeline_class
    )

    for component_name in (
        model_index.keys()
    ):
        if component_name.startswith(
            "_"
        ):
            continue

        if component_name in optional:
            continue

        component_path = (
            model_path
            / component_name
        )

        component_class = (
            _component_class(
                model_index,
                component_name,
            )
        )

        has_weights = (
            _component_has_weights(
                component_path
            )
        )

        if component_class is None:
            # Required components fail closed.
            #
            # If their implementation cannot be
            # resolved and there are no model
            # weights present, do not defer the
            # failure to from_pretrained().
            if not has_weights:
                raise ImageRuntimeError(
                    "A required image-model "
                    "component could not be "
                    "validated and contains no "
                    "model weights: "
                    f"{component_name}"
                )

            continue

        if (
            _class_requires_weights(
                component_class
            )
            and not has_weights
        ):
            raise ImageRuntimeError(
                "A required image-model "
                "component is incomplete: "
                f"{component_name}"
            )



def _version_pair(
    version: str,
) -> tuple[int, int]:
    parts = version.split(
        "."
    )

    numbers: list[int] = []

    for part in parts[:2]:
        digits = "".join(
            character
            for character in part
            if character.isdigit()
        )

        numbers.append(
            int(digits)
            if digits
            else 0
        )

    while len(numbers) < 2:
        numbers.append(0)

    return (
        numbers[0],
        numbers[1],
    )


def _dtype_load_argument(
    *,
    diffusers_module,
    pipeline_class,
    dtype,
) -> tuple[
    dict[str, Any],
    str,
]:
    try:
        signature = inspect.signature(
            pipeline_class
            .from_pretrained
        )
    except (
        TypeError,
        ValueError,
    ):
        signature = None

    if signature is not None:
        if (
            "dtype"
            in signature.parameters
        ):
            return (
                {
                    "dtype": dtype,
                },
                "dtype",
            )

        if (
            "torch_dtype"
            in signature.parameters
        ):
            return (
                {
                    "torch_dtype": (
                        dtype
                    ),
                },
                "torch_dtype",
            )

    version = _version_pair(
        str(
            getattr(
                diffusers_module,
                "__version__",
                "0.0",
            )
        )
    )

    if version >= (0, 40):
        return (
            {
                "dtype": dtype,
            },
            "dtype",
        )

    return (
        {
            "torch_dtype": dtype,
        },
        "torch_dtype",
    )


def _device_and_dtype(
    torch_module,
):
    if (
        torch_module.cuda
        .is_available()
    ):
        return (
            "cuda",
            torch_module.float16,
        )

    return (
        "cpu",
        torch_module.float32,
    )


def _file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _validate_generated_image(
    path: Path,
) -> dict[str, Any]:
    try:
        from PIL import (
            Image,
            ImageStat,
        )
    except ImportError as error:
        raise ImageRuntimeError(
            "Pillow is required for "
            "image validation."
        ) from error

    try:
        with Image.open(
            path
        ) as image:
            image.verify()

        with Image.open(
            path
        ) as image:
            grayscale = image.convert(
                "L"
            )

            statistics = (
                ImageStat.Stat(
                    grayscale
                )
            )

            pixel_std = float(
                statistics.stddev[0]
            )

            width = int(
                image.width
            )

            height = int(
                image.height
            )

    except Exception as error:
        raise ImageRuntimeError(
            "The generated image failed "
            "structural validation."
        ) from error

    return {
        "structural": True,
        "non_degenerate": (
            pixel_std
            >= (
                MINIMUM_PIXEL_STANDARD_DEVIATION
            )
        ),
        "pixel_std": round(
            pixel_std,
            4,
        ),
        "threshold": (
            MINIMUM_PIXEL_STANDARD_DEVIATION
        ),
        "width": width,
        "height": height,
    }


def execute_image_model(
    *,
    model_name: str,
    model_path: Path,
    capability: str,
    runtime_format: str,
    prompt: str,
    output_path: (
        str
        | Path
        | None
    ),
    default_output_directory: Path,
    inference_steps: int,
    width: int,
    height: int,
    seed: int,
) -> dict[str, Any]:
    width = _validate_dimension(
        "width",
        width,
    )

    height = _validate_dimension(
        "height",
        height,
    )

    if (
        not isinstance(
            inference_steps,
            int,
        )
        or isinstance(
            inference_steps,
            bool,
        )
        or not (
            1
            <= inference_steps
            <= 100
        )
    ):
        raise ValueError(
            "inference_steps must be "
            "between 1 and 100."
        )

    if (
        not isinstance(
            seed,
            int,
        )
        or isinstance(
            seed,
            bool,
        )
        or seed < 0
    ):
        raise ValueError(
            "seed must be a "
            "non-negative integer."
        )

    try:
        import diffusers
        import torch
    except ImportError as error:
        raise ImageRuntimeError(
            "Image-generation dependencies "
            "are unavailable."
        ) from error

    resolved_model_path = (
        model_path.resolve()
    )

    model_index = _read_json(
        resolved_model_path
        / "model_index.json"
    )

    pipeline_resolution = (
        _resolve_pipeline_class(
            diffusers,
            model_index,
        )
    )

    pipeline_class = (
        pipeline_resolution[
            "pipeline_class"
        ]
    )

    _validate_required_components(
        pipeline_class=(
            pipeline_class
        ),
        model_index=(
            model_index
        ),
        model_path=(
            resolved_model_path
        ),
    )

    device, dtype = (
        _device_and_dtype(
            torch
        )
    )

    (
        dtype_arguments,
        dtype_keyword,
    ) = _dtype_load_argument(
        diffusers_module=(
            diffusers
        ),
        pipeline_class=(
            pipeline_class
        ),
        dtype=dtype,
    )

    load_arguments: dict[
        str,
        Any,
    ] = {
        "local_files_only": True,
        **dtype_arguments,
    }

    load_arguments.update(
        _component_overrides(
            pipeline_class=(
                pipeline_class
            ),
            model_index=(
                model_index
            ),
            model_path=(
                resolved_model_path
            ),
        )
    )

    if output_path is None:
        destination = (
            default_output_directory
            / model_name
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

    temporary_path = (
        destination.parent
        / (
            f".{destination.stem}."
            f"{uuid4().hex}.tmp.png"
        )
    )

    started_at = (
        time.monotonic()
    )

    pipeline = None

    try:
        pipeline = (
            pipeline_class
            .from_pretrained(
                resolved_model_path,
                **load_arguments,
            )
        )

        pipeline = pipeline.to(
            device
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

        progress_configuration = (
            getattr(
                pipeline,
                "set_progress_bar_config",
                None,
            )
        )

        if callable(
            progress_configuration
        ):
            progress_configuration(
                disable=True
            )

        generator = (
            torch.Generator(
                device=device
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
            raise ImageRuntimeError(
                "The image model returned "
                "no generated image."
            )

        images[0].save(
            temporary_path,
            format="PNG",
        )

        validation = (
            _validate_generated_image(
                temporary_path
            )
        )

        if not validation[
            "non_degenerate"
        ]:
            raise ImageRuntimeError(
                "The generated image failed "
                "non-degenerate validation. "
                "pixel_std="
                f"{validation['pixel_std']}"
            )

        file_hash = (
            _file_sha256(
                temporary_path
            )
        )

        os.replace(
            temporary_path,
            destination,
        )

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()

        raise

    duration_ms = int(
        (
            time.monotonic()
            - started_at
        )
        * 1000
    )

    prompt_hash = hashlib.sha256(
        prompt.encode(
            "utf-8"
        )
    ).hexdigest()

    actual_pipeline_class = (
        pipeline.__class__.__name__
        if pipeline is not None
        else ""
    )

    return {
        "model_name": model_name,
        "model_id": model_name,
        "capability": capability,
        "runtime_format": (
            runtime_format
        ),
        "pipeline_class": (
            actual_pipeline_class
        ),
        "pipeline_resolution": (
            pipeline_resolution[
                "resolution"
            ]
        ),
        "pipeline_fallback_used": (
            pipeline_resolution[
                "fallback_used"
            ]
        ),
        "dtype_keyword": (
            dtype_keyword
        ),
        "device": device,
        "dtype": str(
            dtype
        ).replace(
            "torch.",
            "",
        ),
        "output_type": "image",
        "mime_type": "image/png",
        "output_path": str(
            destination
        ),
        "prompt_hash": (
            prompt_hash
        ),
        "steps": (
            inference_steps
        ),
        "width": width,
        "height": height,
        "seed": seed,
        "duration_ms": (
            duration_ms
        ),
        "sha256": (
            file_hash
        ),
        "validation": (
            validation
        ),
        "runtime_identity": (
            worker_runtime_identity()
        ),
        "image_generated": (
            destination.is_file()
        ),
        "model_loaded": True,
        "training_performed": False,
        "weights_modified": False,
    }
