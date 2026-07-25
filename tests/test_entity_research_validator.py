from datetime import datetime, timezone
from uuid import uuid4

from engine.intelligence.research.entity_research_contracts import (
    EntityResearchResult,
    ResearchFact,
    ResearchSource,
)
from engine.intelligence.research.entity_research_validator import (
    validate_entity_research,
    validate_research_source,
)


def build_source(
    *,
    include_retrieved_text: bool = True,
    include_source_excerpt: bool = True,
) -> ResearchSource:
    token = uuid4().hex
    exact_statement = f"Exact source statement {token}."
    retrieved_text = (
        f"Document opening {token}. "
        f"{exact_statement} "
        f"Document closing {token}."
    )

    return {
        "title": f"Public source {token}",
        "url": f"https://{token}.invalid/document",
        "platform": None,
        "source_type": "public_document",
        "retrieved_text": (
            retrieved_text
            if include_retrieved_text
            else ""
        ),
        "source_excerpt": (
            exact_statement
            if include_source_excerpt
            else ""
        ),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def build_result(
    reviewed_source_total: int,
) -> EntityResearchResult:
    sources = [
        build_source()
        for _ in range(reviewed_source_total)
    ]

    fact_source_urls = (
        [sources[0]["url"]]
        if sources
        else []
    )

    fact: ResearchFact = {
        "text": "A public source contains a supported statement.",
        "source_urls": fact_source_urls,
        "confidence": 0.80,
        "verification_status": "source_reported",
    }

    return {
        "entity_name": f"entity_{uuid4().hex}",
        "summary": "A sourced research summary was produced.",
        "confirmed_facts": [fact],
        "possible_matches": [],
        "public_profiles": [],
        "sources_reviewed": sources,
        "unretrieved_sources": [],
        "source_count": len(sources),
        "searches_performed": [
            f"query_{uuid4().hex}"
        ],
        "limitations": [
            "The available public information is limited."
        ],
        "confidence": 0.80,
        "status": "success",
    }


def test_reviewed_source_requires_retrieved_content() -> None:
    source = build_source(
        include_retrieved_text=False,
        include_source_excerpt=False,
    )

    errors = validate_research_source(source)

    assert errors == [
        "A reviewed source must contain retrieved text "
        "or an exact source excerpt."
    ]


def test_exact_source_excerpt_can_establish_retrieval() -> None:
    source = build_source(
        include_retrieved_text=False,
        include_source_excerpt=True,
    )

    errors = validate_research_source(source)

    assert errors == []


def test_source_excerpt_must_match_retrieved_text() -> None:
    source = build_source()
    source["source_excerpt"] = f"unmatched_{uuid4().hex}"

    errors = validate_research_source(source)

    assert errors == [
        "The source excerpt must be an exact passage "
        "contained in the retrieved text."
    ]


def test_one_source_is_insufficient() -> None:
    result = build_result(reviewed_source_total=1)

    errors = validate_entity_research(result)

    assert errors == [
        "Entity research requires at least two reviewed sources."
    ]


def test_two_valid_sources_pass_validation() -> None:
    result = build_result(reviewed_source_total=2)

    errors = validate_entity_research(result)

    assert errors == []


def test_source_count_must_match_reviewed_sources() -> None:
    result = build_result(reviewed_source_total=2)
    result["source_count"] = 1

    errors = validate_entity_research(result)

    assert (
        "source_count does not match the number of reviewed sources."
        in errors
    )


def test_fact_requires_source_and_confidence() -> None:
    result = build_result(reviewed_source_total=2)
    result["confirmed_facts"][0]["source_urls"] = []
    result["confirmed_facts"][0]["confidence"] = 0.50

    errors = validate_entity_research(result)

    assert any(
        error.startswith("Fact has no supporting source:")
        for error in errors
    )

    assert any(
        error.startswith(
            "Confirmed fact has insufficient confidence:"
        )
        for error in errors
    )


def test_fact_source_must_be_successfully_reviewed() -> None:
    result = build_result(reviewed_source_total=2)
    unknown_url = f"https://{uuid4().hex}.invalid/unretrieved"

    result["confirmed_facts"][0]["source_urls"] = [
        unknown_url
    ]

    errors = validate_entity_research(result)

    assert (
        "Fact references a source that was not successfully "
        f"reviewed: {unknown_url}"
        in errors
    )


def test_vague_summary_requires_limitations() -> None:
    result = build_result(reviewed_source_total=2)
    result["summary"] = (
        "The subject seems to be associated with a public source."
    )
    result["limitations"] = []

    errors = validate_entity_research(result)

    assert (
        "Unsupported uncertainty phrase detected: seems to be"
        in errors
    )
