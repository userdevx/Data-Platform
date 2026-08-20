from uuid import uuid4

from engine.intelligence.search.source_request_parser import (
    SourceSearchRequestParser,
)


def build_entity_name() -> str:
    return f"entity_{uuid4().hex}"


def test_who_is_entity_research_request() -> None:
    entity_name = build_entity_name()

    parsed = SourceSearchRequestParser().parse(
        f"Can you tell me who is {entity_name} "
        "and perform an internet search?"
    )

    assert parsed.query == entity_name
    assert parsed.source == "web"
    assert parsed.requested_output == "bio_summary"
    assert parsed.needs_clarification is False


def test_who_entity_is_research_request() -> None:
    entity_name = build_entity_name()

    parsed = SourceSearchRequestParser().parse(
        f"Can you tell me who {entity_name} is "
        "and perform an internet search?"
    )

    assert parsed.query == entity_name
    assert parsed.source == "web"
    assert parsed.requested_output == "bio_summary"
    assert parsed.needs_clarification is False


def test_common_instruction_typographical_errors() -> None:
    entity_name = build_entity_name()

    parsed = SourceSearchRequestParser().parse(
        f"Can you tell me who {entity_name} is "
        "perfrom a interent search"
    )

    assert parsed.query == entity_name
    assert parsed.source == "web"
    assert parsed.requested_output == "bio_summary"
    assert parsed.needs_clarification is False


def test_basic_search_defaults_to_general_results() -> None:
    entity_name = build_entity_name()

    parsed = SourceSearchRequestParser().parse(
        f"Search for {entity_name}"
    )

    assert parsed.query == entity_name
    assert parsed.source == "web"
    assert parsed.requested_output == "general_results"
    assert parsed.needs_clarification is False


def test_missing_entity_requires_clarification() -> None:
    parsed = SourceSearchRequestParser().parse(
        "Perform an internet search"
    )

    assert parsed.query == ""
    assert parsed.source == "web"
    assert parsed.needs_clarification is True
