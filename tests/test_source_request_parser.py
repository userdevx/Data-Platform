from uuid import uuid4

from engine.intelligence.search.source_request_parser import (
    SourceSearchRequestParser,
)


def test_entity_research_request_does_not_require_clarification() -> None:
    token = uuid4().hex
    entity_name = f"entity_{token}"

    request = (
        f"Can you tell me who is {entity_name} "
        "on the internet and gather information?"
    )

    parsed = SourceSearchRequestParser().parse(
        request
    )

    assert parsed.query == entity_name
    assert parsed.source == "web"
    assert parsed.requested_output == "bio_summary"
    assert parsed.needs_clarification is False


def test_basic_search_defaults_to_general_results() -> None:
    token = uuid4().hex
    entity_name = f"entity_{token}"

    parsed = SourceSearchRequestParser().parse(
        f"Search for {entity_name}"
    )

    assert parsed.query == entity_name
    assert parsed.source == "web"
    assert parsed.requested_output == "general_results"
    assert parsed.needs_clarification is False
