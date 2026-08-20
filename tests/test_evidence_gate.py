from uuid import uuid4

import pytest

from engine.intelligence.search.evidence_gate import (
    build_evidence_context,
    validate_research_evidence,
)


def generated_text(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_blocks_search_result_without_opened_content():
    decision = validate_research_evidence(
        [
            {
                "title": generated_text("title"),
                "url": "https://example.invalid/source",
                "retrieved_text": "",
                "source_excerpt": "",
            }
        ]
    )

    assert decision.allowed is False
    assert decision.evidence == ()


def test_accepts_exact_passage_from_retrieved_content():
    exact_passage = (
        "This exact bounded passage was retrieved from the opened "
        "source and contains enough text for evidence validation."
    )

    decision = validate_research_evidence(
        [
            {
                "title": generated_text("title"),
                "url": "https://example.invalid/source",
                "retrieved_text": (
                    f"Beginning of source. {exact_passage} End of source."
                ),
                "source_excerpt": exact_passage,
            }
        ]
    )

    assert decision.allowed is True
    assert len(decision.evidence) == 1


def test_blocks_passage_not_present_in_retrieved_content():
    decision = validate_research_evidence(
        [
            {
                "title": generated_text("title"),
                "url": "https://example.invalid/source",
                "retrieved_text": generated_text("retrieved"),
                "source_excerpt": (
                    "This passage does not occur inside the retrieved "
                    "source content and must therefore be rejected."
                ),
            }
        ]
    )

    assert decision.allowed is False


def test_requires_requested_number_of_sources():
    exact_passage = (
        "This exact bounded passage is long enough and appears inside "
        "the retrieved source content used by the test."
    )

    decision = validate_research_evidence(
        [
            {
                "title": generated_text("title"),
                "url": "https://example.invalid/source",
                "retrieved_text": exact_passage,
                "source_excerpt": exact_passage,
            }
        ],
        minimum_sources=2,
    )

    assert decision.allowed is False


def test_builds_context_only_from_validated_evidence():
    exact_passage = (
        "This exact source passage provides validated evidence that "
        "can safely be passed into the response generator."
    )

    decision = validate_research_evidence(
        [
            {
                "title": generated_text("title"),
                "url": "https://example.invalid/source",
                "retrieved_text": exact_passage,
                "source_excerpt": exact_passage,
            }
        ]
    )

    context = build_evidence_context(decision)

    assert "Exact passage:" in context
    assert exact_passage in context


def test_rejects_context_build_for_blocked_decision():
    decision = validate_research_evidence([])

    with pytest.raises(ValueError):
        build_evidence_context(decision)
