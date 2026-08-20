from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from engine.intelligence.search.evidence_gate import (
    EvidenceRecord,
    build_evidence_context,
    validate_research_evidence,
)


@dataclass(frozen=True)
class GroundedResearchRequest:
    question: str
    entity: str
    evidence_context: str
    evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True)
class BlockedResearchResponse:
    status: str
    answer: str
    reason: str
    sources: tuple[dict[str, str], ...]


def prepare_grounded_research_request(
    *,
    question: str,
    entity: str,
    raw_records: Iterable[dict[str, Any]],
    minimum_sources: int = 1,
) -> GroundedResearchRequest | BlockedResearchResponse:
    clean_question = " ".join(question.split())
    clean_entity = " ".join(entity.split())

    if not clean_question:
        return BlockedResearchResponse(
            status="blocked",
            answer="A research question is required.",
            reason="missing_question",
            sources=(),
        )

    if not clean_entity:
        return BlockedResearchResponse(
            status="blocked",
            answer="The requested subject could not be identified.",
            reason="missing_entity",
            sources=(),
        )

    decision = validate_research_evidence(
        raw_records,
        minimum_sources=minimum_sources,
    )

    if not decision.allowed:
        return BlockedResearchResponse(
            status="blocked",
            answer=(
                "I could not verify this answer from opened source "
                "content. No factual answer was generated."
            ),
            reason=decision.reason,
            sources=(),
        )

    return GroundedResearchRequest(
        question=clean_question,
        entity=clean_entity,
        evidence_context=build_evidence_context(decision),
        evidence=decision.evidence,
    )


def grounded_system_instruction() -> str:
    return """
Answer only from the validated evidence supplied below.

Rules:
1. Do not use prior knowledge to add factual claims.
2. Do not infer nationality, occupation, identity, dates, or affiliations
   unless the evidence explicitly supports them.
3. Every factual paragraph must be traceable to at least one source.
4. Clearly distinguish direct evidence from cautious inference.
5. Do not say that something is true merely because a search listing
   suggested it.
6. When evidence is insufficient, say that the available opened sources
   do not establish the answer.
7. Do not invent quotations, titles, URLs, dates, relationships, or roles.
8. Do not ask a generic follow-up question merely to hide weak retrieval.
""".strip()
