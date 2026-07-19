from datetime import datetime, timezone
from uuid import uuid4

from engine.intelligence.memory_runtime import (
    get_memory_lookup_predicate,
    is_explicit_memory_command,
    is_memory_lookup_query,
)
from engine.intelligence.models import IntelligenceRequest
from engine.intelligence.router import IntelligenceRouter


def build_request(question: str) -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=f"test_request_{uuid4().hex}",
        created_at=datetime.now(timezone.utc),
        source="test",
        question=question,
        normalized_question=question.lower().strip(),
    )


def test_detects_preferred_implementation_language_query() -> None:
    question = "Which language should implementation examples use?"

    assert is_memory_lookup_query(question)
    assert is_explicit_memory_command(question)
    assert (
        get_memory_lookup_predicate(question)
        == "preferred_implementation_language"
    )


def test_detects_alternative_code_example_wording() -> None:
    questions = [
        "What language should code examples use?",
        "What is my preferred implementation language?",
        "Which language do I prefer for implementation examples?",
        "What language do I prefer for code examples?",
    ]

    for question in questions:
        assert is_memory_lookup_query(question)
        assert (
            get_memory_lookup_predicate(question)
            == "preferred_implementation_language"
        )


def test_unrelated_question_is_not_memory_lookup() -> None:
    question = "Explain the difference between memory and reasoning."

    assert not is_memory_lookup_query(question)
    assert get_memory_lookup_predicate(question) is None


def test_router_selects_memory_before_model_reasoning() -> None:
    router = IntelligenceRouter()
    request = build_request(
        "Which language should implementation examples use?"
    )

    route = router.route(
        request=request,
        enabled_abilities=(
            "manage_memory",
            "model_reasoning",
        ),
        priority=(
            "memory_command",
            "model_reasoning",
        ),
    )

    assert route.ability_name == "manage_memory"
    assert route.reason == "Matched route: memory_command"
    assert route.confidence == 0.90


def test_router_uses_model_for_general_reasoning() -> None:
    router = IntelligenceRouter()
    request = build_request(
        "Explain the difference between memory and reasoning."
    )

    route = router.route(
        request=request,
        enabled_abilities=(
            "manage_memory",
            "model_reasoning",
        ),
        priority=(
            "memory_command",
            "model_reasoning",
        ),
    )

    assert route.ability_name == "model_reasoning"
