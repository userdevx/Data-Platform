from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.visual_model.provider_configuration import (
    load_visual_model_registry_configuration,
)
from services.visual_model.provider_errors import (
    VisualProviderError,
)
from services.visual_model.provider_factory import (
    build_visual_provider_registry,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

DEFAULT_CONFIGURATION_PATH = (
    PROJECT_ROOT
    / "config"
    / "visual_model"
    / "registry.json"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the configured visual "
            "provider registry."
        )
    )

    parser.add_argument(
        "--configuration",
        default=str(
            DEFAULT_CONFIGURATION_PATH
        ),
    )

    parser.add_argument(
        "--discover",
        action="store_true",
        help=(
            "Perform explicit provider discovery. "
            "This may contact enabled providers."
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        configuration = (
            load_visual_model_registry_configuration(
                Path(
                    arguments.configuration
                ).expanduser().resolve()
            )
        )

        registry = (
            build_visual_provider_registry(
                configuration
            )
        )

        record: dict[str, object] = {
            "status": "configured",
            "enabled": configuration.enabled,
            "providers": list(
                registry.provider_ids()
            ),
            "selection_policy": {
                "prefer_local": (
                    configuration
                    .selection_policy
                    .prefer_local
                ),
                "allow_cloud_fallback": (
                    configuration
                    .selection_policy
                    .allow_cloud_fallback
                ),
                "require_runtime_health_check": (
                    configuration
                    .selection_policy
                    .require_runtime_health_check
                ),
                "maximum_attempts": (
                    configuration
                    .selection_policy
                    .maximum_attempts
                ),
            },
            "models": [],
            "errors": [],
        }

        if arguments.discover:
            record["models"] = [
                {
                    "provider_id": (
                        model.provider_id
                    ),
                    "model_id": model.model_id,
                    "capabilities": sorted(
                        model.capabilities
                    ),
                    "processing_location": (
                        model
                        .processing_location
                        .value
                    ),
                    "status": (
                        model.status.value
                    ),
                    "structured_output": (
                        model
                        .supports_structured_output
                    ),
                }
                for model in (
                    registry.discover_models()
                )
            ]

        print(
            json.dumps(
                record,
                ensure_ascii=False,
            )
        )

        return 0

    except (
        OSError,
        ValueError,
        VisualProviderError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "errors": [
                        str(error)
                    ],
                },
                ensure_ascii=False,
            )
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
