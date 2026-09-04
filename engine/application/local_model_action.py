from __future__ import annotations

from engine.application.local_model_worker import (
    execute_local_model_worker,
    worker_runtime_identity,
)

import base64
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from engine.generation.bindings import (
    build_job_record_store,
)
from engine.generation.models import (
    FailureReason,
    GenerationProfile,
    JobState,
    SAFE_BASELINE,
)
from engine.generation.service import (
    GenerationJobService,
)
from engine.model_development.runtime import (
    IMAGE_GENERATION,
    TEXT_GENERATION,
    discover_base_models,
    resolve_base_model,
)
from services.visual_model.provider_errors import (
    VisualProviderUnavailableError,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

MODEL_PYTHON = (
    PROJECT_ROOT
    / "venv-training"
    / "bin"
    / "python"
)

LOCAL_MODEL_PROVIDER_ID = (
    "local_artifact"
)

GENERATION_POLL_INTERVAL_SECONDS = 0.25
GENERATION_WAIT_TIMEOUT_SECONDS = 1860


def is_local_model_provider(
    provider_id: str,
) -> bool:
    return (
        provider_id.strip()
        == LOCAL_MODEL_PROVIDER_ID
    )


def build_local_model_options(
) -> list[dict[str, object]]:
    if not MODEL_PYTHON.is_file():
        return []

    return [
        {
            "option_id": (
                f"{LOCAL_MODEL_PROVIDER_ID}:"
                f"{model.name}"
            ),
            "provider_id": (
                LOCAL_MODEL_PROVIDER_ID
            ),
            "model_id": model.name,
            "display_name": (
                f"Local — {model.name}"
            ),
            "processing_location": (
                "local"
            ),
            "available": True,
            "capabilities": [
                model.capability
            ],
        }
        for model
        in discover_base_models()
        if model.capability
        in {
            TEXT_GENERATION,
            IMAGE_GENERATION,
        }
    ]


def find_local_models_by_capability(
    capability: str,
) -> tuple[str, ...]:
    clean_capability = (
        capability.strip().lower()
    )

    return tuple(
        model.name
        for model
        in discover_base_models()
        if (
            model.capability
            == clean_capability
        )
    )


def _parse_worker_response(
    output: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            output.strip()
        )
    except json.JSONDecodeError as error:
        raise VisualProviderUnavailableError(
            "The local model worker "
            "returned invalid JSON."
        ) from error

    if not isinstance(
        payload,
        dict,
    ):
        raise VisualProviderUnavailableError(
            "The local model worker "
            "returned an invalid response."
        )

    return payload


def _execute_worker(
    *,
    model_id: str,
    question: str,
    capability: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if not MODEL_PYTHON.is_file():
        raise VisualProviderUnavailableError(
            "The local model execution "
            "environment is unavailable."
        )

    try:
        return execute_local_model_worker(
            model_python=MODEL_PYTHON,
            project_root=PROJECT_ROOT,
            model_id=model_id,
            question=question,
            capability=capability,
            arguments=arguments,
        )

    except Exception as error:
        raise VisualProviderUnavailableError(
            str(error)
        ) from error




def _generation_profile(
    arguments: dict[str, Any],
) -> GenerationProfile:
    profile_fields = {
        "steps",
        "width",
        "height",
        "seed",
        "guidance_scale",
        "negative_prompt",
        "scheduler",
        "vae_tiling",
        "attention_slicing",
        "strength",
        "name",
    }

    overrides = {
        key: value
        for key, value
        in arguments.items()
        if key in profile_fields
    }

    if not overrides:
        return SAFE_BASELINE

    return GenerationProfile(
        **overrides
    )


def _artifact_output_path(
    relative_path: str,
) -> Path:
    path = Path(
        relative_path
    )

    if not path.is_absolute():
        path = (
            PROJECT_ROOT
            / path
        )

    resolved = path.resolve()

    if not resolved.is_relative_to(
        PROJECT_ROOT.resolve()
    ):
        raise VisualProviderUnavailableError(
            "The generated artifact is "
            "outside the application root."
        )

    return resolved


def _execute_generation_job(
    *,
    model_id: str,
    question: str,
    request_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    job_arguments = dict(
        arguments
    )

    for profile_key in (
        "steps",
        "width",
        "height",
        "seed",
        "guidance_scale",
        "negative_prompt",
        "scheduler",
        "vae_tiling",
        "attention_slicing",
        "strength",
        "name",
    ):
        job_arguments.pop(
            profile_key,
            None,
        )

    profile = _generation_profile(
        arguments
    )

    store = build_job_record_store()

    service = GenerationJobService(
        store=store,
        project_root=PROJECT_ROOT,
    )

    job = service.submit(
        capability=IMAGE_GENERATION,
        prompt=question,
        model_id=model_id,
        profile=profile,
        request_id=request_id,
        arguments=job_arguments,
        detach=True,
    )

    if job.state is JobState.REJECTED:
        detail = str(
            job.arguments.get(
                "rejection_detail",
                "",
            )
        ).strip()

        raise VisualProviderUnavailableError(
            detail
            or (
                "The generation request "
                "was rejected."
            )
        )

    timeout_value = job_arguments.get(
        "timeout_seconds",
        GENERATION_WAIT_TIMEOUT_SECONDS
        - 60,
    )

    try:
        worker_timeout = int(
            timeout_value
        )
    except (
        TypeError,
        ValueError,
    ):
        worker_timeout = (
            GENERATION_WAIT_TIMEOUT_SECONDS
            - 60
        )

    wait_timeout = max(
        1,
        worker_timeout + 60,
    )

    deadline = (
        time.monotonic()
        + wait_timeout
    )

    current = job

    while (
        current.state
        not in {
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.REJECTED,
        }
    ):
        if (
            time.monotonic()
            >= deadline
        ):
            service.cancel(
                job.job_id,
                reason=(
                    FailureReason.TIMEOUT
                ),
            )

            raise VisualProviderUnavailableError(
                "The bounded generation "
                "request exceeded its "
                "application wait limit."
            )

        time.sleep(
            GENERATION_POLL_INTERVAL_SECONDS
        )

        refreshed = service.get(
            job.job_id
        )

        if refreshed is None:
            raise VisualProviderUnavailableError(
                "The GenerationJob could "
                "not be recovered from "
                "the Data Engine."
            )

        current = refreshed

    if (
        current.state
        is not JobState.SUCCEEDED
    ):
        detail = str(
            current.arguments.get(
                "failure_detail",
                current.arguments.get(
                    "rejection_detail",
                    "",
                ),
            )
        ).strip()

        if (
            current.state
            is JobState.CANCELLED
        ):
            raise VisualProviderUnavailableError(
                "The generation request "
                "was cancelled."
            )

        raise VisualProviderUnavailableError(
            detail
            or (
                "The bounded generation "
                f"request ended as "
                f"{current.state.value}."
            )
        )

    artifact_id = str(
        current.artifact_id
        or ""
    ).strip()

    if not artifact_id:
        raise VisualProviderUnavailableError(
            "The completed GenerationJob "
            "returned no artifact identity."
        )

    artifact = service.artifact(
        artifact_id
    )

    if artifact is None:
        raise VisualProviderUnavailableError(
            "The generated artifact could "
            "not be recovered from the "
            "Data Engine."
        )

    value = artifact.get(
        "value",
        {},
    )

    if not isinstance(
        value,
        dict,
    ):
        raise VisualProviderUnavailableError(
            "The generated artifact record "
            "is invalid."
        )

    relative_path = str(
        value.get(
            "relative_path",
            "",
        )
    ).strip()

    output_path = (
        _artifact_output_path(
            relative_path
        )
    )

    resources = value.get(
        "resources",
        {},
    )

    if not isinstance(
        resources,
        dict,
    ):
        resources = {}

    validation = value.get(
        "validation",
        {},
    )

    if not isinstance(
        validation,
        dict,
    ):
        validation = {}

    return {
        "status": "success",
        "job_id": current.job_id,
        "request_id": current.request_id,
        "artifact_id": artifact_id,
        "model_name": model_id,
        "model_id": model_id,
        "capability": IMAGE_GENERATION,
        "runtime_format": str(
            value.get(
                "runtime_format",
                "",
            )
        ),
        "pipeline_class": str(
            value.get(
                "pipeline_class",
                "",
            )
        ),
        "device": str(
            value.get(
                "device",
                "",
            )
        ),
        "dtype": str(
            value.get(
                "dtype",
                "",
            )
        ),
        "output_type": "image",
        "mime_type": str(
            value.get(
                "mime_type",
                "image/png",
            )
        ),
        "output_path": str(
            output_path
        ),
        "sha256": str(
            value.get(
                "sha256",
                "",
            )
        ),
        "validation": validation,
        "profile": value.get(
            "profile",
            current.profile.as_dict(),
        ),
        "memory_peak_bytes": (
            resources.get(
                "memory_peak_bytes"
            )
        ),
        "duration_ms": (
            resources.get(
                "duration_ms"
            )
        ),
    }


def _image_data_url(
    path_value: str,
) -> str:
    path = Path(
        path_value
    ).resolve()

    root = PROJECT_ROOT.resolve()

    if not path.is_file():
        raise VisualProviderUnavailableError(
            "The generated image file "
            "does not exist."
        )

    if not path.is_relative_to(
        root
    ):
        raise VisualProviderUnavailableError(
            "The generated image is "
            "outside the application root."
        )

    encoded = base64.b64encode(
        path.read_bytes()
    ).decode(
        "ascii"
    )

    return (
        "data:image/png;base64,"
        f"{encoded}"
    )


def process_local_model_request(
    *,
    question: str,
    model_id: str,
    requested_capability: str = "",
    arguments: dict[str, Any] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    descriptor = resolve_base_model(
        model_id
    )

    selected_capability = (
        requested_capability
        .strip()
        .lower()
        or descriptor.capability
    )

    if (
        selected_capability
        != descriptor.capability
    ):
        raise VisualProviderUnavailableError(
            "The selected local model "
            "does not support the "
            "requested capability."
        )

    request_arguments = dict(
        arguments or {}
    )

    effective_request_id = (
        request_id.strip()
        or str(
            request_arguments.pop(
                "request_id",
                "",
            )
        ).strip()
    )

    if (
        selected_capability
        == IMAGE_GENERATION
    ):
        result = _execute_generation_job(
            model_id=model_id,
            question=question,
            request_id=(
                effective_request_id
            ),
            arguments=(
                request_arguments
            ),
        )

    else:
        result = _execute_worker(
            model_id=model_id,
            question=question,
            capability=(
                selected_capability
            ),
            arguments=(
                request_arguments
            ),
        )

    output_type = str(
        result.get(
            "output_type",
            "",
        )
    ).strip()

    if output_type == "text":
        answer = str(
            result.get(
                "generated_text",
                "",
            )
        ).strip()

        if not answer:
            raise VisualProviderUnavailableError(
                "The local text model "
                "returned no response."
            )

    elif output_type == "image":
        output_path = str(
            result.get(
                "output_path",
                "",
            )
        ).strip()

        result[
            "image_data_url"
        ] = _image_data_url(
            output_path
        )

        answer = (
            "Image generated."
        )

    else:
        raise VisualProviderUnavailableError(
            "The local model returned "
            "an unsupported output type."
        )

    return {
        "status": "success",
        "answer": answer,
        "results": [],
        "raw": {
            "status": "success",
            "answer": answer,
            "route": (
                "manual_model_selection"
            ),
            "source": (
                LOCAL_MODEL_PROVIDER_ID
            ),
            "capability": (
                selected_capability
            ),
            "provider_id": (
                LOCAL_MODEL_PROVIDER_ID
            ),
            "model_id": (
                descriptor.name
            ),
            "processing_location": (
                "local"
            ),
            "records_used": [],
            "insights": [],
            "metadata": result,
        },
    }
