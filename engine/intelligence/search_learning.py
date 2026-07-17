from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from engine.intelligence.memory_runtime import (
    build_memory_service,
    get_intelligence_id,
    get_user_id,
    is_memory_enabled,
)
from engine.memory.models import MemoryCandidate, MemoryKind
from engine.memory.service import MemoryRejectedError


@dataclass(slots=True)
class SourceTrustEvaluation:
    learnable: bool
    score: float
    reason: str
    domain: str
    source_type: str


class DynamicSourceTrustEvaluator:
    """
    Scores whether a public search result is learnable.

    This does not use a hardcoded trusted-domain list.
    Trust is calculated from observable result quality signals.
    """

    def evaluate(
        self,
        *,
        query: str,
        target_source: str,
        result: dict[str, Any],
    ) -> SourceTrustEvaluation:
        title = str(result.get("title", "")).strip()
        url = str(result.get("url", "")).strip()
        result_source = str(result.get("source", "")).strip()
        result_score = result.get("score", 0)

        parsed = urlparse(url)
        domain = parsed.netloc.lower().strip()

        if not title:
            return SourceTrustEvaluation(
                learnable=False,
                score=0.0,
                reason="missing_title",
                domain=domain,
                source_type="unknown",
            )

        if not url:
            return SourceTrustEvaluation(
                learnable=False,
                score=0.0,
                reason="missing_url",
                domain=domain,
                source_type="unknown",
            )

        if parsed.scheme not in {"http", "https"}:
            return SourceTrustEvaluation(
                learnable=False,
                score=0.0,
                reason="unsupported_url_scheme",
                domain=domain,
                source_type="unknown",
            )

        if not domain or "." not in domain:
            return SourceTrustEvaluation(
                learnable=False,
                score=0.0,
                reason="invalid_domain",
                domain=domain,
                source_type="unknown",
            )

        if self._looks_unsafe(url):
            return SourceTrustEvaluation(
                learnable=False,
                score=0.0,
                reason="unsafe_url_pattern",
                domain=domain,
                source_type="unknown",
            )

        trust_score = 0.25
        source_type = "public_web"

        if title:
            trust_score += 0.15

        if url:
            trust_score += 0.15

        if result_source:
            trust_score += 0.10

        if isinstance(result_score, (int, float)) and result_score > 0:
            trust_score += min(float(result_score) / 100.0, 0.20)

        if target_source and self._domain_matches_target_source(
            domain=domain,
            target_source=target_source,
        ):
            trust_score += 0.25
            source_type = "target_aligned_public_source"

        if query and self._title_matches_query(title=title, query=query):
            trust_score += 0.15

        trust_score = min(trust_score, 1.0)
        learnable = trust_score >= 0.55

        return SourceTrustEvaluation(
            learnable=learnable,
            score=trust_score,
            reason="accepted" if learnable else "low_trust_score",
            domain=domain,
            source_type=source_type,
        )

    @staticmethod
    def _domain_matches_target_source(
        *,
        domain: str,
        target_source: str,
    ) -> bool:
        clean_target = target_source.lower().strip()

        if not clean_target:
            return False

        compact_domain = domain.replace("www.", "")
        compact_target = clean_target.replace(" ", "")

        return compact_target in compact_domain

    @staticmethod
    def _title_matches_query(
        *,
        title: str,
        query: str,
    ) -> bool:
        title_tokens = {
            token.lower()
            for token in title.replace("(", " ").replace(")", " ").split()
            if len(token) > 1
        }

        query_tokens = {
            token.lower()
            for token in query.split()
            if len(token) > 1
        }

        if not query_tokens:
            return False

        return bool(title_tokens.intersection(query_tokens))

    @staticmethod
    def _looks_unsafe(url: str) -> bool:
        lowered = url.lower()

        unsafe_patterns = [
            "javascript:",
            "data:",
            "file:",
            "blob:",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "@",
        ]

        return any(pattern in lowered for pattern in unsafe_patterns)


def create_search_memory_candidate(
    *,
    user_id: str,
    intelligence_id: str,
    query: str,
    target_source: str,
    result: dict[str, Any],
    trust: SourceTrustEvaluation,
    source_request_id: str | None = None,
) -> MemoryCandidate:
    title = str(result.get("title", "")).strip()
    url = str(result.get("url", "")).strip()
    source = str(result.get("source", "")).strip()

    value = {
        "query": query,
        "target_source": target_source,
        "title": title,
        "url": url,
        "source": source,
        "domain": trust.domain,
        "source_type": trust.source_type,
        "trust_score": trust.score,
        "trust_reason": trust.reason,
    }

    canonical_text = (
        f"For the search query '{query}', a public result was found: "
        f"{title} ({url})."
    )

    predicate = "known_public_profile" if target_source else "learned_public_source"

    return MemoryCandidate(
        user_id=user_id,
        intelligence_id=intelligence_id,
        namespace="public_search_learning",
        kind=MemoryKind.EPISODIC,
        subject="public_search",
        predicate=predicate,
        value=value,
        canonical_text=canonical_text,
        confidence=max(0.75, min(trust.score, 0.95)),
        importance=0.72,
        source_conversation_id="public_search",
        source_message_id=source_request_id,
        source_text=canonical_text,
        explicit_request=False,
        metadata={
            "learned_from": "public_source_search",
            "target_source": target_source,
            "domain": trust.domain,
            "source_type": trust.source_type,
            "trust_score": trust.score,
            "trust_reason": trust.reason,
        },
    )


def learn_from_public_search_result(
    *,
    root,
    definition: Any,
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    if not is_memory_enabled(definition):
        return {
            "learning_enabled": False,
            "created": 0,
            "rejected": [],
            "evaluations": [],
        }

    data = response_payload.get("data", {})

    if not isinstance(data, dict):
        return {
            "learning_enabled": True,
            "created": 0,
            "rejected": ["missing_data"],
            "evaluations": [],
        }

    results = data.get("results", [])

    if not isinstance(results, list):
        return {
            "learning_enabled": True,
            "created": 0,
            "rejected": ["missing_results"],
            "evaluations": [],
        }

    query = str(data.get("query", "")).strip()
    target_source = str(data.get("target_source", "")).strip()

    if not query:
        return {
            "learning_enabled": True,
            "created": 0,
            "rejected": ["missing_query"],
            "evaluations": [],
        }

    service = build_memory_service(root)
    evaluator = DynamicSourceTrustEvaluator()

    created = 0
    rejected: list[str] = []
    evaluations: list[dict[str, Any]] = []

    for result in results[:3]:
        if not isinstance(result, dict):
            continue

        trust = evaluator.evaluate(
            query=query,
            target_source=target_source,
            result=result,
        )

        evaluations.append(
            {
                "domain": trust.domain,
                "learnable": trust.learnable,
                "score": trust.score,
                "reason": trust.reason,
                "source_type": trust.source_type,
            }
        )

        if not trust.learnable:
            rejected.append(trust.reason)
            continue

        candidate = create_search_memory_candidate(
            user_id=get_user_id(),
            intelligence_id=get_intelligence_id(definition),
            query=query,
            target_source=target_source,
            result=result,
            trust=trust,
            source_request_id=response_payload.get("request_id"),
        )

        try:
            memory = service.remember(candidate)

            if memory is not None:
                created += 1

        except MemoryRejectedError as error:
            rejected.append(str(error))

    return {
        "learning_enabled": True,
        "created": created,
        "rejected": rejected,
        "evaluations": evaluations,
    }
