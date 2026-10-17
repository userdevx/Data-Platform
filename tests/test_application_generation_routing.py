from engine.intelligence.generation_request import (
    APPLICATION_GENERATION,
    IMAGE_GENERATION,
    TEXT_INPUT,
    resolve_generation_capability,
)
from engine.intelligence.models import (
    IntelligenceRequest,
)
from engine.intelligence.router import (
    IntelligenceRouter,
)


def _route(
    question: str,
):
    request = (
        IntelligenceRequest.create(
            question=question,
            source="test",
        )
    )

    return IntelligenceRouter().route(
        request=request,
        enabled_abilities=(
            "application_generation",
            "model_reasoning",
        ),
        priority=(
            "application_generation",
            "model_reasoning",
        ),
    )


def test_application_generation_classifier() -> None:
    assert (
        resolve_generation_capability(
            "Create a software application "
            "that processes structured input."
        )
        == APPLICATION_GENERATION
    )


def test_program_generation_classifier() -> None:
    assert (
        resolve_generation_capability(
            "Build a command line program."
        )
        == APPLICATION_GENERATION
    )


def test_image_generation_preserved() -> None:
    assert (
        resolve_generation_capability(
            "Generate an image of a city."
        )
        == IMAGE_GENERATION
    )


def test_generic_writing_remains_text() -> None:
    assert (
        resolve_generation_capability(
            "Write a summary of the report."
        )
        == TEXT_INPUT
    )


def test_application_route_precedes_model_reasoning() -> None:
    route = _route(
        "Create a software application "
        "that accepts JSON input."
    )

    assert (
        route.ability_name
        == "application_generation"
    )


def test_generic_writing_uses_model_reasoning() -> None:
    route = _route(
        "Write a summary of the report."
    )

    assert (
        route.ability_name
        == "model_reasoning"
    )
