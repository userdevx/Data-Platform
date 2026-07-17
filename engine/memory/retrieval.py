from __future__ import annotations

import re
from datetime import datetime

from engine.memory.models import MemoryKind, MemoryRecord, utc_now


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


class MemoryRetriever:
    def retrieve(
        self,
        *,
        query: str,
        memories: list[MemoryRecord],
        limit: int = 12,
        now: datetime | None = None,
    ) -> list[MemoryRecord]:
        current_time = now or utc_now()
        query_tokens = self._tokenize(query)

        scored: list[tuple[float, MemoryRecord]] = []

        for memory in memories:
            if not memory.is_current(current_time):
                continue

            score = self._score(
                memory=memory,
                query_tokens=query_tokens,
                now=current_time,
            )

            if score <= 0:
                continue

            scored.append((score, memory))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].importance,
                item[1].confidence,
                item[1].updated_at,
            ),
            reverse=True,
        )

        return self._remove_redundancy(
            [memory for _, memory in scored],
            limit=limit,
        )

    def _score(
        self,
        *,
        memory: MemoryRecord,
        query_tokens: set[str],
        now: datetime,
    ) -> float:
        memory_tokens = self._tokenize(
            " ".join(
                [
                    memory.subject,
                    memory.predicate,
                    memory.canonical_text,
                    str(memory.value),
                ]
            )
        )

        lexical_score = self._jaccard(query_tokens, memory_tokens)

        predicate_tokens = self._tokenize(memory.predicate.replace("_", " "))
        predicate_score = self._jaccard(query_tokens, predicate_tokens)

        age_days = max(0.0, (now - memory.updated_at).total_seconds() / 86_400)
        recency_score = 1.0 / (1.0 + age_days / 90.0)

        procedural_boost = 0.25 if memory.kind is MemoryKind.PROCEDURAL else 0.0
        explicit_boost = 0.15 if memory.metadata.get("explicit_request") else 0.0
        project_rule_boost = 0.15 if memory.predicate == "project_rule" else 0.0

        base_score = (
            0.30 * lexical_score
            + 0.20 * predicate_score
            + 0.15 * memory.importance
            + 0.10 * memory.confidence
            + 0.10 * recency_score
            + procedural_boost
            + explicit_boost
            + project_rule_boost
        )

        if not query_tokens.intersection(memory_tokens):
            if memory.kind is MemoryKind.PROCEDURAL:
                return base_score * 0.80

            return base_score * 0.25

        return base_score

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(text)
            if len(token) > 1
        }

    @staticmethod
    def _jaccard(first: set[str], second: set[str]) -> float:
        if not first or not second:
            return 0.0

        union = len(first.union(second))

        if union == 0:
            return 0.0

        return len(first.intersection(second)) / union

    @staticmethod
    def _remove_redundancy(
        memories: list[MemoryRecord],
        *,
        limit: int,
    ) -> list[MemoryRecord]:
        selected: list[MemoryRecord] = []
        identities: set[tuple[str, str, str]] = set()

        for memory in memories:
            identity = (memory.namespace, memory.subject, memory.predicate)

            if identity in identities:
                continue

            selected.append(memory)
            identities.add(identity)

            if len(selected) >= limit:
                break

        return selected
