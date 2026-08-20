from uuid import uuid4

from engine.intelligence.search.grounded_response import (
    BlockedResearchResponse,
    GroundedResearchRequest,
)
from engine.intelligence.search.research_pipeline import (
    prepare_entity_research_result,
)


def dynamic_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_blocks_result_without_retrieved_sources() -> None:
    result = prepare_entity_research_result(
        user_question=dynamic_value("question"),
        parsed_entity=dynamic_value("entity"),
        research_result={
            "sources_reviewed": [],
            "unretrieved_sources": [
                {
                    "title": dynamic_value("title"),
                    "url": "https://example.invalid/source",
                }
            ],
        },
    )

    assert isinstance(result, BlockedResearchResponse)
    assert result.status == "blocked"


def test_accepts_result_with_exact_opened_source_content() -> None:
    exact_passage = (
        "This exact bounded passage appears inside the retrieved "
        "source content and supports the requested factual response."
    )

    result = prepare_entity_research_result(
        user_question=dynamic_value("question"),
        parsed_entity=dynamic_value("entity"),
        research_result={
            "sources_reviewed": [
                {
                    "title": dynamic_value("title"),
                    "url": "https://example.invalid/source",
                    "retrieved_text": (
                        f"Opening text. {exact_passage} Closing text."
                    ),
                    "source_excerpt": exact_passage,
                }
            ],
            "unretrieved_sources": [],
        },
    )

    assert isinstance(result, GroundedResearchRequest)
    assert exact_passage in result.evidence_context


def test_blocks_invalid_source_container() -> None:
    result = prepare_entity_research_result(
        user_question=dynamic_value("question"),
        parsed_entity=dynamic_value("entity"),
        research_result={
            "sources_reviewed": "invalid",
        },
    )

    assert isinstance(result, BlockedResearchResponse)


def test_can_require_multiple_opened_sources() -> None:
    exact_passage = (
        "This exact passage is sufficiently long and appears inside "
        "the retrieved source content."
    )

    result = prepare_entity_research_result(
        user_question=dynamic_value("question"),
        parsed_entity=dynamic_value("entity"),
        research_result={
            "sources_reviewed": [
                {
                    "title": dynamic_value("title"),
                    "url": "https://example.invalid/source",
                    "retrieved_text": exact_passage,
                    "source_excerpt": exact_passage,
                }
            ]
        },
        minimum_sources=2,
    )

    assert isinstance(result, BlockedResearchResponse)
