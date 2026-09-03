from __future__ import annotations


TEXT_INPUT = "text_input"
IMAGE_GENERATION = (
    "image_generation"
)


def resolve_generation_capability(
    text: str,
) -> str:
    normalized = " ".join(
        str(text)
        .lower()
        .split()
    ).strip()

    if not normalized:
        return TEXT_INPUT

    image_terms = (
        "image",
        "picture",
        "photo",
        "illustration",
        "drawing",
        "artwork",
        "graphic",
        "render",
    )

    generation_actions = (
        "create",
        "generate",
        "make",
        "draw",
        "render",
        "produce",
        "show",
    )

    has_image_subject = any(
        term in normalized
        for term
        in image_terms
    )

    has_generation_action = any(
        action in normalized
        for action
        in generation_actions
    )

    if (
        has_image_subject
        and has_generation_action
    ):
        return IMAGE_GENERATION

    return TEXT_INPUT
