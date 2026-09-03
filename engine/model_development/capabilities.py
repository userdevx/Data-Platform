from __future__ import annotations

from enum import Enum


class ModelCapability(
    str,
    Enum,
):
    TEXT_GENERATION = (
        "text_generation"
    )

    IMAGE_GENERATION = (
        "image_generation"
    )

    UNKNOWN = "unknown"


class ModelRuntimeFormat(
    str,
    Enum,
):
    TRANSFORMERS = "transformers"

    DIFFUSERS = "diffusers"

    UNKNOWN = "unknown"
