from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.application.environment import (
    load_project_environment,
)
from engine.application.model_options import (
    build_model_options,
)
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

REGISTRY_CONFIGURATION_PATH = (
    PROJECT_ROOT
    / "config"
    / "visual_model"
    / "registry.json"
)


def get_model_options() -> dict[str, Any]:
    load_project_environment()

    try:
        configuration = (
            load_visual_model_registry_configuration(
                REGISTRY_CONFIGURATION_PATH
            )
        )

        registry = build_visual_provider_registry(
            configuration
        )

        return {
            "status": "success",
            "models": build_model_options(
                registry
            ),
            "errors": [],
        }

    except (
        OSError,
        ValueError,
        VisualProviderError,
    ) as error:
        return {
            "status": "error",
            "models": [],
            "errors": [
                str(error),
            ],
        }
