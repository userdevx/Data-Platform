from __future__ import annotations

import re


TEXT_INPUT = "text_input"
IMAGE_GENERATION = (
    "image_generation"
)


def _tokenize(
    text: str,
) -> frozenset[str]:
    return frozenset(
        re.findall(
            r"[a-z0-9]+",
            str(text).lower(),
        )
    )


def resolve_generation_capability(
    text: str,
) -> str:
    tokens = _tokenize(
        text
    )

    if not tokens:
        return TEXT_INPUT

    image_terms = frozenset(
        {
            "image",
            "picture",
            "photo",
            "illustration",
            "drawing",
            "artwork",
            "graphic",
            "render",
        }
    )

    generation_actions = frozenset(
        {
            "create",
            "generate",
            "make",
            "draw",
            "render",
            "produce",
            "show",
        }
    )

    has_image_subject = bool(
        tokens
        & image_terms
    )

    has_generation_action = bool(
        tokens
        & generation_actions
    )

    if (
        has_image_subject
        and has_generation_action
    ):
        return IMAGE_GENERATION

    return TEXT_INPUT
