from __future__ import annotations

from dataclasses import asdict, dataclass

from services.visual_model.provider_contracts import (
    ModelStatus,
)
from services.visual_model.provider_registry import (
    VisualProviderRegistry,
)


@dataclass(frozen=True)
class ModelOption:
    option_id: str
    provider_id: str
    model_id: str
    display_name: str
    processing_location: str
    available: bool
    capabilities: tuple[str, ...]


def build_model_options(
    registry: VisualProviderRegistry,
) -> list[dict[str, object]]:
    options: list[ModelOption] = [
        ModelOption(
            option_id="automatic",
            provider_id="",
            model_id="",
            display_name="Automatic",
            processing_location="automatic",
            available=True,
            capabilities=(),
        )
    ]

    for model in registry.discover_models():
        if not model.enabled:
            continue

        available = (
            model.status is ModelStatus.AVAILABLE
        )

        options.append(
            ModelOption(
                option_id=(
                    f"{model.provider_id}:"
                    f"{model.model_id}"
                ),
                provider_id=model.provider_id,
                model_id=model.model_id,
                display_name=_build_display_name(
                    provider_id=model.provider_id,
                    model_id=model.model_id,
                    processing_location=(
                        model.processing_location.value
                    ),
                ),
                processing_location=(
                    model.processing_location.value
                ),
                available=available,
                capabilities=tuple(
                    sorted(model.capabilities)
                ),
            )
        )

    return [
        asdict(option)
        for option in options
    ]


def _build_display_name(
    *,
    provider_id: str,
    model_id: str,
    processing_location: str,
) -> str:
    location_label = {
        "local": "Local",
        "private_remote": "Private",
        "cloud": "Cloud",
    }.get(
        processing_location,
        processing_location.title(),
    )

    provider_label = (
        provider_id
        .replace("-", " ")
        .replace("_", " ")
        .title()
    )

    return (
        f"{location_label} — "
        f"{provider_label} — "
        f"{model_id}"
    )
