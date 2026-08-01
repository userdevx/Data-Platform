from __future__ import annotations

import json
from pathlib import Path

from services.visual_model.__main__ import (
    main,
)


def write_configuration_files(
    tmp_path: Path,
) -> tuple[Path, Path]:
    runtime_path = (
        tmp_path / "runtime.json"
    )

    runtime_path.write_text(
        json.dumps(
            {
                "private_visual_runtime": {
                    "enabled": False,
                    "runtime_type": (
                        "private_visual_runtime"
                    ),
                    "provider_name": "",
                    "model_id": "",
                    "model_path": "",
                    "maximum_output_tokens": 256,
                    "initialization_timeout_seconds": 10,
                    "inference_timeout_seconds": 10,
                }
            }
        ),
        encoding="utf-8",
    )

    service_path = (
        tmp_path / "service.json"
    )

    service_path.write_text(
        json.dumps(
            {
                "visual_model_service": {
                    "enabled": False,
                    "maximum_image_size_bytes": 4096,
                    "allowed_media_types": [
                        "image/png"
                    ],
                    "require_healthy_runtime": True,
                },
                "visual_model_transport": {
                    "backend_name": "",
                    "host": "127.0.0.1",
                    "port": 0,
                    "service_path": "/runtime",
                    "maximum_request_payload_size_bytes": 8192,
                    "maximum_response_payload_size_bytes": 8192,
                },
            }
        ),
        encoding="utf-8",
    )

    return runtime_path, service_path


def test_status_command_reports_disabled_runtime(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    runtime_path, service_path = (
        write_configuration_files(
            tmp_path
        )
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "visual-model-service",
            "status",
            "--runtime-configuration",
            str(runtime_path),
            "--service-configuration",
            str(service_path),
        ],
    )

    exit_code = main()

    output = json.loads(
        capsys.readouterr().out
    )

    assert exit_code == 0
    assert output["status"] == "unavailable"
    assert (
        output["runtime"]["enabled"]
        is False
    )
    assert (
        output["service"]["host"]
        == "127.0.0.1"
    )


def test_invalid_configuration_returns_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    invalid_path = (
        tmp_path / "invalid.json"
    )

    invalid_path.write_text(
        "{}",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "visual-model-service",
            "status",
            "--runtime-configuration",
            str(invalid_path),
            "--service-configuration",
            str(invalid_path),
        ],
    )

    exit_code = main()

    output = json.loads(
        capsys.readouterr().out
    )

    assert exit_code == 1
    assert output["status"] == "error"
    assert output["errors"]
