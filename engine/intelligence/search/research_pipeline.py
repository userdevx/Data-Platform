from __future__ import annotations

from typing import Any, Iterable

from engine.intelligence.search.grounded_response import (
    BlockedResearchResponse,
    GroundedResearchRequest,
    prepare_grounded_research_request,
)


def prepare_research_response(
    *,
    user_question: str,
    parsed_entity: str,
    retrieved_sources: Iterable[dict[str, Any]],
    minimum_sources: int = 1,
) -> GroundedResearchRequest | BlockedResearchResponse:
    return prepare_grounded_research_request(
        question=user_question,
        entity=parsed_entity,
        raw_records=retrieved_sources,
        minimum_sources=minimum_sources,
    )


def prepare_entity_research_result(
    *,
    user_question: str,
    parsed_entity: str,
    research_result: dict[str, Any],
    minimum_sources: int = 1,
) -> GroundedResearchRequest | BlockedResearchResponse:
    reviewed_sources = research_result.get(
        "sources_reviewed",
        [],
    )

    if not isinstance(reviewed_sources, list):
        return BlockedResearchResponse(
            status="blocked",
            answer=(
                "I could not verify this answer from opened source "
                "content. No factual answer was generated."
            ),
            reason=(
                "The research result did not contain a valid "
                "sources_reviewed list."
            ),
            sources=(),
        )

    retrieved_sources = [
        source
        for source in reviewed_sources
        if isinstance(source, dict)
        and source.get("retrieved_text")
        and source.get("source_excerpt")
    ]

    return prepare_research_response(
        user_question=user_question,
        parsed_entity=parsed_entity,
        retrieved_sources=retrieved_sources,
        minimum_sources=minimum_sources,
    )
