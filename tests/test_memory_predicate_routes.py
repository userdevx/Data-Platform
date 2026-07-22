from pathlib import Path

from engine.memory.predicate_routes import (
    load_predicate_routes,
    match_predicate_route,
    normalize_lookup_text,
)


ROOT = Path(__file__).resolve().parents[1]


def test_loads_all_configured_routes() -> None:
    routes = load_predicate_routes(root=ROOT)

    assert set(routes) == {
        "preferred_implementation_language",
        "preferred_response_style",
        "preferred_display_name",
    }


def test_matches_implementation_language_route() -> None:
    route = match_predicate_route(
        root=ROOT,
        text="Which language should implementation examples use?",
    )

    assert route is not None
    assert route.predicate == "preferred_implementation_language"
    assert route.namespace == "implementation_preferences"
    assert route.subject == "user"
    assert route.answer_mode == "value"


def test_matches_response_style_route() -> None:
    route = match_predicate_route(
        root=ROOT,
        text="How should responses be formatted?",
    )

    assert route is not None
    assert route.predicate == "preferred_response_style"
    assert route.namespace == "interaction_preferences"
    assert route.subject == "user"


def test_matches_display_name_route() -> None:
    route = match_predicate_route(
        root=ROOT,
        text="What is my preferred display name?",
    )

    assert route is not None
    assert route.predicate == "preferred_display_name"
    assert route.namespace == "identity_preferences"
    assert route.subject == "user"


def test_unrelated_question_does_not_match() -> None:
    route = match_predicate_route(
        root=ROOT,
        text="Explain the Data Engine.",
    )

    assert route is None


def test_normalizes_case_spacing_and_punctuation() -> None:
    result = normalize_lookup_text(
        "  WHICH language should implementation examples use?!  "
    )

    assert result == (
        "which language should implementation examples use"
    )
