from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Measured on this host: qwen3:8b answered "Reply with: ok" using
# 722 tokens with thinking enabled and 2 with it disabled.
DEFAULT_CONTEXT_CAPACITY = 8192
DEFAULT_RESPONSE_RESERVE = 2048

CHARACTERS_PER_TOKEN = 3.5

DEFAULT_MINIMUM_RELEVANCE = 0.3
DEFAULT_MAXIMUM_CANDIDATE_SHARE = 0.4


def estimate_tokens(text: str) -> int:
    return int(len(text or "") / CHARACTERS_PER_TOKEN) + 1


@dataclass(frozen=True)
class ContextCandidate:
    """
    One retrievable item, whatever produced it.

    record_id keeps the Data Engine authoritative: the candidate
    carries enough text to be ranked and rendered, and the record
    remains the source of truth.
    """

    record_id: str
    data_type: str
    text: str
    retrieval_source: str          # recency | lexical | vector | agentic
    relevance: float = 0.0         # 0..1, comparable within a source
    recency_rank: int = 0          # 0 = most recent
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)

    @property
    def value_per_token(self) -> float:
        return self.relevance / max(1, self.tokens)

    def as_provenance(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "data_type": self.data_type,
            "retrieval_source": self.retrieval_source,
            "relevance": self.relevance,
            "recency_rank": self.recency_rank,
            "tokens": self.tokens,
            "value_per_token": round(
                self.value_per_token, 6
            ),
        }


@dataclass(frozen=True)
class ContextBudget:
    capacity: int
    response_reserve: int
    system_tokens: int
    question_tokens: int
    available_tokens: int

    def as_measurements(self) -> dict[str, Any]:
        return {
            "context_capacity": self.capacity,
            "response_reserve": self.response_reserve,
            "system_tokens": self.system_tokens,
            "question_tokens": self.question_tokens,
            "available_tokens": self.available_tokens,
        }


@dataclass(frozen=True)
class ContextSelection:
    selected: tuple[ContextCandidate, ...]
    rejected: tuple[ContextCandidate, ...]
    tokens_used: int
    budget: ContextBudget
    rejection_reasons: dict[str, str] = field(
        default_factory=dict
    )
    minimum_relevance: float = 0.0
    maximum_candidate_tokens: int = 0

    def render(self) -> str:
        if not self.selected:
            return ""
        body = "\n".join(item.text for item in self.selected)
        return (
            "<conversation_context>\n"
            + body
            + "\n</conversation_context>"
        )

    def as_measurements(self) -> dict[str, Any]:
        by_source: dict[str, int] = {}
        for item in self.selected:
            by_source[item.retrieval_source] = (
                by_source.get(item.retrieval_source, 0) + 1
            )

        return {
            **self.budget.as_measurements(),
            "candidate_count": (
                len(self.selected) + len(self.rejected)
            ),
            "selected_count": len(self.selected),
            "rejected_count": len(self.rejected),
            "tokens_used": self.tokens_used,
            "within_budget": (
                self.tokens_used <= self.budget.available_tokens
            ),
            "selected_by_source": by_source,
            "minimum_relevance": self.minimum_relevance,
            "maximum_candidate_tokens": (
                self.maximum_candidate_tokens
            ),
            "rejected_by_reason": {
                reason: sum(
                    1
                    for value
                    in self.rejection_reasons.values()
                    if value == reason
                )
                for reason in sorted(
                    set(self.rejection_reasons.values())
                )
            },
            "mean_value_per_token_selected": round(
                sum(
                    item.value_per_token
                    for item in self.selected
                )
                / max(1, len(self.selected)),
                6,
            ),
            "selected_record_ids": [
                item.record_id for item in self.selected
            ],
            "provenance": [
                item.as_provenance() for item in self.selected
            ],
        }


class ContextWindowManager:
    """
    Bounds retrieval so it cannot overflow the model's real window.

    context_capacity must equal the num_ctx sent to Ollama. If they
    disagree the server silently evicts the oldest tokens -- the
    retrieved records -- and every budget measurement becomes fiction.
    """

    def __init__(
        self,
        *,
        context_capacity: int = DEFAULT_CONTEXT_CAPACITY,
        response_reserve: int = DEFAULT_RESPONSE_RESERVE,
        minimum_relevance: float = (
            DEFAULT_MINIMUM_RELEVANCE
        ),
        maximum_candidate_share: float = (
            DEFAULT_MAXIMUM_CANDIDATE_SHARE
        ),
    ) -> None:
        if context_capacity < 512:
            raise ValueError("context_capacity is implausibly small.")

        if response_reserve >= context_capacity:
            raise ValueError(
                "response_reserve must be smaller than context_capacity."
            )

        self.context_capacity = context_capacity
        self.response_reserve = response_reserve
        self.minimum_relevance = minimum_relevance
        self.maximum_candidate_share = (
            maximum_candidate_share
        )

    def budget(
        self,
        *,
        system_prompt: str,
        question: str,
    ) -> ContextBudget:
        system_tokens = estimate_tokens(system_prompt)
        question_tokens = estimate_tokens(question)

        return ContextBudget(
            capacity=self.context_capacity,
            response_reserve=self.response_reserve,
            system_tokens=system_tokens,
            question_tokens=question_tokens,
            available_tokens=max(
                0,
                self.context_capacity
                - self.response_reserve
                - system_tokens
                - question_tokens,
            ),
        )

    @staticmethod
    def _priority(candidate: ContextCandidate) -> tuple:
        # Value per token, not raw relevance. A 40-token fact at 0.7
        # is worth far more than a 570-token transcript at 0.7,
        # because it leaves room for everything behind it.
        return (
            -candidate.value_per_token,
            -candidate.relevance,
            candidate.recency_rank,
        )

    def fit(
        self,
        candidates: list[ContextCandidate],
        *,
        budget: ContextBudget,
    ) -> ContextSelection:
        """
        Admit candidates by value per token, subject to a relevance
        floor and a per-record size ceiling.
        """

        seen: set[str] = set()
        ordered = sorted(candidates, key=self._priority)

        maximum_candidate_tokens = int(
            budget.available_tokens
            * self.maximum_candidate_share
        )

        selected: list[ContextCandidate] = []
        rejected: list[ContextCandidate] = []
        reasons: dict[str, str] = {}
        used = 0

        for candidate in ordered:
            if candidate.record_id in seen:
                rejected.append(candidate)
                reasons[candidate.record_id] = "duplicate"
                continue

            if candidate.relevance < self.minimum_relevance:
                rejected.append(candidate)
                reasons[candidate.record_id] = "below_relevance"
                continue

            cost = candidate.tokens

            if cost > maximum_candidate_tokens:
                rejected.append(candidate)
                reasons[candidate.record_id] = "oversized"
                continue

            if used + cost > budget.available_tokens:
                rejected.append(candidate)
                reasons[candidate.record_id] = "budget_exhausted"
                continue

            seen.add(candidate.record_id)
            selected.append(candidate)
            used += cost

        return ContextSelection(
            selected=tuple(selected),
            rejected=tuple(rejected),
            tokens_used=used,
            budget=budget,
            rejection_reasons=reasons,
            minimum_relevance=self.minimum_relevance,
            maximum_candidate_tokens=maximum_candidate_tokens,
        )
