from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.intelligence.vision.config import (
    VisualConfiguration,
    load_visual_configuration,
)
from engine.intelligence.vision.media_validation import (
    validate_media_file,
)
from engine.intelligence.vision.provider_registry import (
    VisualAnalyzerRegistry,
)
from engine.intelligence.vision.runtime import VisualRuntime
from engine.intelligence.vision.still_image_source import (
    StillImageSource,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CONFIGURATION_PATH = (
    PROJECT_ROOT
    / "config"
    / "vision"
    / "active.json"
)


def build_response(
    *,
    status: str,
    answer: str,
    data: dict[str, Any] | None = None,
    errors: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "status": status,
        "answer": answer,
        "data": data or {},
        "errors": list(errors),
    }


def configuration_to_record(
    configuration: VisualConfiguration,
) -> dict[str, Any]:
    return {
        "enabled": configuration.enabled,
        "provider": configuration.provider,
        "model": configuration.model,
        "maximum_media_size_bytes": (
            configuration.maximum_media_size_bytes
        ),
        "sampling": asdict(
            configuration.sampling
        ),
        "validation": asdict(
            configuration.validation
        ),
        "storage": asdict(
            configuration.storage
        ),
    }


def load_configuration(
    configuration_path: Path,
) -> VisualConfiguration:
    return load_visual_configuration(
        configuration_path
    )


def get_visual_status(
    *,
    configuration_path: Path,
) -> dict[str, Any]:
    try:
        configuration = load_configuration(
            configuration_path
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return build_response(
            status="configuration_error",
            answer=(
                "The visual runtime configuration "
                "could not be loaded."
            ),
            errors=(str(error),),
        )

    if not configuration.enabled:
        return build_response(
            status="disabled",
            answer=(
                "Visual analysis is disabled by "
                "the active configuration."
            ),
            data={
                "configuration": (
                    configuration_to_record(
                        configuration
                    )
                ),
            },
        )

    if not configuration.provider:
        return build_response(
            status="unavailable",
            answer=(
                "No visual-analysis provider "
                "is configured."
            ),
            data={
                "configuration": (
                    configuration_to_record(
                        configuration
                    )
                ),
            },
        )

    return build_response(
        status="ready",
        answer=(
            "The visual runtime is configured."
        ),
        data={
            "configuration": (
                configuration_to_record(
                    configuration
                )
            ),
        },
    )


def analyze_image(
    *,
    image_path: Path,
    query: str,
    source_reference: str | None,
    configuration_path: Path,
) -> dict[str, Any]:
    clean_query = " ".join(
        query.split()
    ).strip()

    if not clean_query:
        return build_response(
            status="rejected",
            answer=(
                "A visual-analysis question "
                "is required."
            ),
            errors=("query is required",),
        )

    try:
        configuration = load_configuration(
            configuration_path
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return build_response(
            status="configuration_error",
            answer=(
                "The visual runtime configuration "
                "could not be loaded."
            ),
            errors=(str(error),),
        )

    media_validation = validate_media_file(
        media_path=image_path,
        maximum_size_bytes=(
            configuration
            .maximum_media_size_bytes
        ),
    )

    if not media_validation.allowed:
        return build_response(
            status="invalid_media",
            answer=(
                "The selected media could not "
                "be validated. No visual claims "
                "were generated."
            ),
            data={
                "media": {
                    "path": str(image_path),
                    "media_type": (
                        media_validation.media_type
                    ),
                    "size_bytes": (
                        media_validation.size_bytes
                    ),
                },
            },
            errors=(
                media_validation.reason,
            ),
        )

    registry = VisualAnalyzerRegistry()

    analyzer = registry.create(
        configuration.provider
    )

    records: list[
        dict[str, Any]
    ] = []

    runtime = VisualRuntime(
        analyzer=analyzer,
        configuration=configuration,
        record_writer=records.append,
    )

    source = StillImageSource(
        media_path=image_path,
        media_type=(
            media_validation.media_type
        ),
        source_id=uuid4().hex,
        sequence_id=uuid4().hex,
    )

    frame = next(
        iter(source.frames())
    )

    result = runtime.process_frame(
        frame=frame,
        query=clean_query,
        media_mode="single_image",
        source_reference=source_reference,
    )

    observation_record = (
        result.observation.to_record()
        if result.observation is not None
        else None
    )

    return build_response(
        status=result.status,
        answer=result.answer,
        data={
            "observation": observation_record,
            "records": list(
                result.records
            ),
            "media": {
                "path": str(image_path),
                "media_type": (
                    media_validation.media_type
                ),
                "size_bytes": (
                    media_validation.size_bytes
                ),
            },
        },
        errors=result.errors,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Application bridge for "
            "visual processing."
        )
    )

    parser.add_argument(
        "command",
        choices=(
            "status",
            "analyze-image",
        ),
    )

    parser.add_argument(
        "--image-path",
        default="",
    )

    parser.add_argument(
        "--query",
        default="",
    )

    parser.add_argument(
        "--source-reference",
        default="",
    )

    parser.add_argument(
        "--configuration",
        default=str(
            DEFAULT_CONFIGURATION_PATH
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    configuration_path = Path(
        arguments.configuration
    ).expanduser().resolve()

    if arguments.command == "status":
        result = get_visual_status(
            configuration_path=(
                configuration_path
            ),
        )
    else:
        image_path = Path(
            arguments.image_path
        ).expanduser().resolve()

        result = analyze_image(
            image_path=image_path,
            query=arguments.query,
            source_reference=(
                arguments.source_reference
                or None
            ),
            configuration_path=(
                configuration_path
            ),
        )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
        )
    )

    failure_statuses = {
        "configuration_error",
        "provider_error",
    }

    return (
        1
        if result["status"]
        in failure_statuses
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
