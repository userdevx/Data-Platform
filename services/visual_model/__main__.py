from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.visual_model.backend_registry import (
    PrivateVisualBackendRegistry,
)
from services.visual_model.bootstrap import (
    DEFAULT_RUNTIME_CONFIGURATION_PATH,
    DEFAULT_SERVICE_CONFIGURATION_PATH,
    assemble_visual_model_service,
)
from services.visual_model.errors import (
    VisualModelServiceError,
)
from services.visual_model.transport import (
    serve_forever,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Private visual model service."
        )
    )

    parser.add_argument(
        "command",
        choices=(
            "status",
            "serve",
        ),
    )

    parser.add_argument(
        "--runtime-configuration",
        default=str(
            DEFAULT_RUNTIME_CONFIGURATION_PATH
        ),
    )

    parser.add_argument(
        "--service-configuration",
        default=str(
            DEFAULT_SERVICE_CONFIGURATION_PATH
        ),
    )

    return parser.parse_args()


def build_backend_registry(
) -> PrivateVisualBackendRegistry:
    return PrivateVisualBackendRegistry()


def status_record(
    assembly,
) -> dict:
    health = assembly.coordinator.health_check()

    return {
        "status": (
            "ready"
            if health.available
            else "unavailable"
        ),
        "service": {
            "enabled": (
                assembly
                .service_configuration
                .enabled
            ),
            "host": (
                assembly
                .transport_configuration
                .host
            ),
            "port": (
                assembly
                .transport_configuration
                .port
            ),
            "service_path": (
                assembly
                .transport_configuration
                .service_path
            ),
        },
        "runtime": {
            "enabled": (
                assembly
                .runtime_configuration
                .enabled
            ),
            "runtime_type": (
                assembly
                .runtime_configuration
                .runtime_type
            ),
            "provider": health.provider,
            "model_id": health.model_id,
            "available": health.available,
            "message": health.message,
        },
        "errors": [],
    }


def main() -> int:
    arguments = parse_arguments()

    runtime_configuration_path = Path(
        arguments.runtime_configuration
    ).expanduser().resolve()

    service_configuration_path = Path(
        arguments.service_configuration
    ).expanduser().resolve()

    registry = build_backend_registry()

    try:
        assembly = assemble_visual_model_service(
            backend_registry=registry,
            runtime_configuration_path=(
                runtime_configuration_path
            ),
            service_configuration_path=(
                service_configuration_path
            ),
        )

        if arguments.command == "status":
            result = status_record(
                assembly
            )

            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
            )

            return 0

        serve_forever(
            service=assembly.service,
            configuration=(
                assembly
                .transport_configuration
            ),
        )

        return 0

    except VisualModelServiceError as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "errors": [
                        str(error),
                    ],
                },
                ensure_ascii=False,
            )
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
