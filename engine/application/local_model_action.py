from __future__ import annotations

from engine.application.local_model_worker import (
    execute_local_model_worker,
    worker_runtime_identity,
)

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

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

    result = _execute_worker(
        model_id=model_id,
        question=question,
        capability=(
            selected_capability
        ),
        arguments=dict(
            arguments or {}
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
