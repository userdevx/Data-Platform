from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any


IMAGE_GENERATION = (
    "image_generation"
)

DEFAULT_TEXT_TIMEOUT_SECONDS = 60
DEFAULT_IMAGE_TIMEOUT_SECONDS = 180


class LocalModelWorkerError(
    RuntimeError
):
    pass


def _positive_environment_integer(
    name: str,
    default: int,
) -> int:
    raw_value = os.environ.get(
        name,
        "",
    ).strip()

    if not raw_value:
        return default

    try:
        parsed = int(
            raw_value
        )
    except ValueError:
        return default

    return (
        parsed
        if parsed > 0
        else default
    )


def _worker_threads(
    capability: str,
) -> int:
    if (
        capability
        == IMAGE_GENERATION
    ):
        return max(
            1,
            (
                os.cpu_count()
                or 4
            )
            - 1,
        )

    return 2


def build_worker_environment(
    *,
    project_root: Path,
    capability: str,
) -> dict[str, str]:
    environment = dict(
        os.environ
    )

    threads = _worker_threads(
        capability
    )

    environment.update(
        {
            "PYTHONPATH": str(
                project_root
            ),
            "PYTHONUNBUFFERED": "1",
            (
                "TOKENIZERS_PARALLELISM"
            ): "false",
            "OMP_NUM_THREADS": str(
                threads
            ),
            "OPENBLAS_NUM_THREADS": str(
                threads
            ),
            "MKL_NUM_THREADS": str(
                threads
            ),
            "NUMEXPR_NUM_THREADS": str(
                threads
            ),
        }
    )

    return environment


def parse_worker_json(
    standard_output: str,
) -> dict[str, Any]:
    lines = [
        line.strip()
        for line
        in standard_output.splitlines()
        if line.strip()
    ]

    for line in reversed(
        lines
    ):
        try:
            value = json.loads(
                line
            )
        except json.JSONDecodeError:
            continue

        if isinstance(
            value,
            dict,
        ):
            return value

    raise LocalModelWorkerError(
        "The local model worker "
        "returned no JSON object."
    )


def _argument_integer(
    arguments: dict[str, Any],
    names: tuple[str, ...],
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value: Any = None

    for name in names:
        if name in arguments:
            raw_value = (
                arguments[name]
            )
            break

    if raw_value is None:
        return default

    if (
        not isinstance(
            raw_value,
            int,
        )
        or isinstance(
            raw_value,
            bool,
        )
        or not (
            minimum
            <= raw_value
            <= maximum
        )
    ):
        raise ValueError(
            f"{names[0]} must be between "
            f"{minimum} and {maximum}."
        )

    return raw_value


def worker_runtime_identity(
    *,
    model_python: Path,
    project_root: Path,
) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(
                model_python
            ),
            "-m",
            (
                "engine."
                "model_development."
                "worker_cli"
            ),
            "identity",
        ],
        cwd=project_root,
        env=build_worker_environment(
            project_root=(
                project_root
            ),
            capability=(
                IMAGE_GENERATION
            ),
        ),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if completed.returncode != 0:
        diagnostic = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or (
                "Worker identity "
                "request failed."
            )
        )

        raise LocalModelWorkerError(
            diagnostic[-8000:]
        )

    return parse_worker_json(
        completed.stdout
    )


def execute_local_model_worker(
    *,
    model_python: Path,
    project_root: Path,
    model_id: str,
    question: str,
    capability: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    command = [
        str(
            model_python
        ),
        "-m",
        (
            "engine."
            "model_development."
            "worker_cli"
        ),
        "execute",
        "--model",
        model_id,
        "--prompt",
        question,
    ]

    if (
        capability
        == IMAGE_GENERATION
    ):
        steps = _argument_integer(
            arguments,
            (
                "steps",
                "inference_steps",
            ),
            default=8,
            minimum=1,
            maximum=100,
        )

        width = _argument_integer(
            arguments,
            ("width",),
            default=256,
            minimum=64,
            maximum=1024,
        )

        height = _argument_integer(
            arguments,
            ("height",),
            default=256,
            minimum=64,
            maximum=1024,
        )

        seed = _argument_integer(
            arguments,
            ("seed",),
            default=17,
            minimum=0,
            maximum=(
                2**31 - 1
            ),
        )

        command.extend(
            [
                "--steps",
                str(
                    steps
                ),
                "--width",
                str(
                    width
                ),
                "--height",
                str(
                    height
                ),
                "--seed",
                str(
                    seed
                ),
            ]
        )

        timeout_seconds = (
            _positive_environment_integer(
                (
                    "LOCAL_IMAGE_MODEL_"
                    "REQUEST_TIMEOUT_SECONDS"
                ),
                DEFAULT_IMAGE_TIMEOUT_SECONDS,
            )
        )

    else:
        max_new_tokens = (
            _argument_integer(
                arguments,
                ("max_new_tokens",),
                default=128,
                minimum=1,
                maximum=256,
            )
        )

        command.extend(
            [
                "--max-new-tokens",
                str(
                    max_new_tokens
                ),
            ]
        )

        timeout_seconds = (
            _positive_environment_integer(
                (
                    "LOCAL_TEXT_MODEL_"
                    "REQUEST_TIMEOUT_SECONDS"
                ),
                DEFAULT_TEXT_TIMEOUT_SECONDS,
            )
        )

    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            env=build_worker_environment(
                project_root=(
                    project_root
                ),
                capability=(
                    capability
                ),
            ),
            capture_output=True,
            text=True,
            timeout=(
                timeout_seconds
            ),
            check=False,
        )

    except subprocess.TimeoutExpired as error:
        raise LocalModelWorkerError(
            "The local model worker "
            "exceeded "
            f"{timeout_seconds} seconds."
        ) from error

    if completed.returncode != 0:
        diagnostic = (
            completed.stderr.strip()
            or completed.stdout.strip()
            or (
                "The local model worker "
                "failed."
            )
        )

        raise LocalModelWorkerError(
            diagnostic[-8000:]
        )

    payload = parse_worker_json(
        completed.stdout
    )

    if (
        payload.get("status")
        != "success"
    ):
        errors = payload.get(
            "errors",
            [],
        )

        raise LocalModelWorkerError(
            "; ".join(
                str(error)
                for error in errors
            )
            or (
                "The local model worker "
                "returned an error."
            )
        )

    return payload
