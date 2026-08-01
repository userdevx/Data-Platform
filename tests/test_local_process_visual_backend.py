from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Mapping

import pytest

from services.visual_model.errors import (
    VisualModelRuntimeError,
)
from services.visual_model.providers.local_process_backend import (
    LocalProcessVisualBackend,
    LocalProcessVisualBackendConfiguration,
)


def create_model_file(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "model.bin"
    path.write_bytes(
        b"local-model"
    )
    return path


def create_backend_program(
    tmp_path: Path,
    body: str,
) -> Path:
    path = tmp_path / "backend-program.py"

    path.write_text(
        "#!/usr/bin/env python3\n"
        "import base64\n"
        "import json\n"
        "import sys\n"
        f"{body}\n",
        encoding="utf-8",
    )

    path.chmod(
        path.stat().st_mode
        | stat.S_IXUSR
    )

    return path


def build_backend(
    program_path: Path,
    *,
    maximum_response_size_bytes: int = 4096,
) -> LocalProcessVisualBackend:
    return LocalProcessVisualBackend(
        configuration=(
            LocalProcessVisualBackendConfiguration(
                executable_path=str(
                    program_path
                ),
                maximum_response_size_bytes=(
                    maximum_response_size_bytes
                ),
            )
        )
    )


def initialize_backend(
    backend: LocalProcessVisualBackend,
    model_path: Path,
) -> None:
    backend.initialize(
        model_path=model_path,
        model_id="runtime-model",
        initialization_timeout_seconds=10,
    )


def analyze_backend(
    backend: LocalProcessVisualBackend,
):
    return backend.analyze(
        question="Describe the visible evidence.",
        image_data=b"image-data",
        media_type="image/png",
        response_schema={
            "type": "object",
        },
        maximum_output_tokens=256,
        inference_timeout_seconds=5,
    )


def test_successful_local_process_analysis(
    tmp_path: Path,
) -> None:
    program = create_backend_program(
        tmp_path,
        """
request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
image_data = base64.b64decode(
    request["input"]["image_base64"]
)
assert image_data == b"image-data"
response = {
    "status": "success",
    "result": {
        "scene_description": "runtime scene",
        "entities": [
            {
                "entity_id": "entity-1",
                "label": "runtime label",
                "confidence": 0.91
            }
        ],
        "relations": [],
        "visible_text": ["runtime text"],
        "uncertainty": [],
        "warnings": [],
        "metadata": {
            "backend": "local-process"
        }
    }
}
sys.stdout.write(json.dumps(response))
""",
    )

    backend = build_backend(program)
    initialize_backend(
        backend,
        create_model_file(tmp_path),
    )

    result = analyze_backend(backend)

    assert (
        result.scene_description
        == "runtime scene"
    )
    assert len(result.entities) == 1
    assert result.visible_text == (
        "runtime text",
    )
    assert (
        result.metadata["backend"]
        == "local-process"
    )


def test_backend_is_unavailable_before_initialization(
    tmp_path: Path,
) -> None:
    program = create_backend_program(
        tmp_path,
        "sys.stdout.write('{}')",
    )

    backend = build_backend(program)

    assert backend.is_available() is False

    with pytest.raises(
        VisualModelRuntimeError,
        match="not been initialized",
    ):
        analyze_backend(backend)


def test_missing_executable_is_rejected(
    tmp_path: Path,
) -> None:
    backend = build_backend(
        tmp_path / "missing-program"
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="does not exist",
    ):
        initialize_backend(
            backend,
            create_model_file(tmp_path),
        )


def test_non_executable_file_is_rejected(
    tmp_path: Path,
) -> None:
    program = tmp_path / "program.py"
    program.write_text(
        "print('test')",
        encoding="utf-8",
    )

    backend = build_backend(program)

    with pytest.raises(
        VisualModelRuntimeError,
        match="not executable",
    ):
        initialize_backend(
            backend,
            create_model_file(tmp_path),
        )


def test_process_failure_is_wrapped(
    tmp_path: Path,
) -> None:
    program = create_backend_program(
        tmp_path,
        "raise SystemExit(2)",
    )

    backend = build_backend(program)
    initialize_backend(
        backend,
        create_model_file(tmp_path),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="failure status",
    ):
        analyze_backend(backend)


def test_invalid_json_is_rejected(
    tmp_path: Path,
) -> None:
    program = create_backend_program(
        tmp_path,
        "sys.stdout.write('not-json')",
    )

    backend = build_backend(program)
    initialize_backend(
        backend,
        create_model_file(tmp_path),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="invalid JSON",
    ):
        analyze_backend(backend)


def test_backend_reported_failure_is_rejected(
    tmp_path: Path,
) -> None:
    program = create_backend_program(
        tmp_path,
        """
sys.stdout.write(
    json.dumps(
        {
            "status": "error",
            "result": {}
        }
    )
)
""",
    )

    backend = build_backend(program)
    initialize_backend(
        backend,
        create_model_file(tmp_path),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="reported an inference failure",
    ):
        analyze_backend(backend)


def test_oversized_response_is_rejected(
    tmp_path: Path,
) -> None:
    program = create_backend_program(
        tmp_path,
        """
sys.stdout.write(
    json.dumps(
        {
            "status": "success",
            "result": {
                "scene_description": "x" * 1000
            }
        }
    )
)
""",
    )

    backend = build_backend(
        program,
        maximum_response_size_bytes=100,
    )

    initialize_backend(
        backend,
        create_model_file(tmp_path),
    )

    with pytest.raises(
        VisualModelRuntimeError,
        match="exceeded the maximum size",
    ):
        analyze_backend(backend)


def test_backend_uses_no_shell_execution() -> None:
    source = Path(
        "services/visual_model/providers/"
        "local_process_backend.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "shell=True" not in source
