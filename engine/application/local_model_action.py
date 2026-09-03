from __future__ import annotations

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
) -> dict[str, Any]:
    if not MODEL_PYTHON.is_file():
        raise VisualProviderUnavailableError(
            "The local model execution "
            "environment is unavailable."
        )

    command = [
        str(MODEL_PYTHON),
        "-m",
        "engine.model_development",
        "test",
        "--model",
        model_id,
        "--prompt",
        question,
        "--max-new-tokens",
        "128",
        "--steps",
        "6",
        "--width",
        "384",
        "--height",
        "384",
        "--seed",
        "17",
    ]

    environment = dict(
        os.environ
    )

    environment[
        "PYTHONPATH"
    ] = str(
        PROJECT_ROOT
    )

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=55,
        check=False,
    )

    if completed.returncode != 0:
        diagnostic = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or "Local model execution failed."
        )

        raise VisualProviderUnavailableError(
            diagnostic[-4000:]
        )

    return _parse_worker_response(
        completed.stdout
    )


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
) -> dict[str, Any]:
    descriptor = (
        resolve_base_model(
            model_id
        )
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
            "required capability."
        )

    result = _execute_worker(
        model_id=model_id,
        question=question,
    )

    output_type = str(
        result.get(
            "output_type",
            "",
        )
    )

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
        )

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
            "an unsupported output."
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
