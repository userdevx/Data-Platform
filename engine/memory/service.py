from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any
from uuid import UUID

from engine.memory.context_builder import MemoryContextBuilder
from engine.memory.models import (
    MemoryCandidate,
    MemoryOperation,
    MemoryRecord,
    MemoryStatus,
    utc_now,
)
from engine.memory.predicates import PredicateCardinality, get_predicate_definition
from engine.memory.repository import MemoryRepository
from engine.memory.retrieval import MemoryRetriever
from engine.memory.validation import MemoryValidator


class MemoryRejectedError(ValueError):
    pass


class MemoryNotFoundError(LookupError):
    pass


class MemoryService:
    def __init__(
        self,
        *,
        repository: MemoryRepository,
        validator: MemoryValidator,
        retriever: MemoryRetriever,
        context_builder: MemoryContextBuilder,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._retriever = retriever
        self._context_builder = context_builder

    def remember(self, candidate: MemoryCandidate) -> MemoryRecord | None:
        validation, candidate = self._validator.validate(candidate)

        if not validation.should_store:
            raise MemoryRejectedError(validation.reason or "memory_rejected")

        if candidate.operation is MemoryOperation.IGNORE:
            return None

        if candidate.operation is MemoryOperation.RETRACT:
            self.forget_matching(
                user_id=candidate.user_id,
                intelligence_id=candidate.intelligence_id,
                namespace=candidate.namespace,
                subject=candidate.subject,
                predicate=candidate.predicate,
                value=candidate.value,
            )
            return None

        predicate = get_predicate_definition(candidate.predicate)

        if predicate is None:
            raise MemoryRejectedError("unknown_predicate")

        existing = self._repository.find_identity_matches(
            user_id=candidate.user_id,
            intelligence_id=candidate.intelligence_id,
            namespace=candidate.namespace,
            subject=candidate.subject,
            predicate=candidate.predicate,
        )

        equivalent = self._find_equivalent(existing, candidate.value)

        if equivalent is not None:
            confirmed = replace(
                equivalent,
                confidence=min(0.99, max(equivalent.confidence, candidate.confidence) + 0.02),
                importance=max(equivalent.importance, candidate.importance),
                updated_at=utc_now(),
                metadata={
                    **equivalent.metadata,
                    "explicit_request": (
                        equivalent.metadata.get("explicit_request", False)
                        or candidate.explicit_request
                    ),
                    "confirmation_count": int(
                        equivalent.metadata.get("confirmation_count", 1)
                    )
                    + 1,
                },
            )

            return self._repository.replace(confirmed)

        superseded_memory_id: UUID | None = None

        if predicate.cardinality is PredicateCardinality.ONE and existing:
            for current in existing:
                self._repository.mark_superseded(current)

            superseded_memory_id = existing[0].memory_id

        new_memory = MemoryRecord(
            user_id=candidate.user_id,
            intelligence_id=candidate.intelligence_id,
            kind=candidate.kind,
            namespace=candidate.namespace,
            subject=candidate.subject,
            predicate=candidate.predicate,
            value=candidate.value,
            canonical_text=candidate.canonical_text,
            confidence=candidate.confidence,
            importance=candidate.importance,
            sensitivity=validation.sensitivity,
            source_conversation_id=candidate.source_conversation_id,
            source_message_id=candidate.source_message_id,
            source_text_hash=self._hash_source(candidate.source_text),
            valid_from=candidate.valid_from,
            valid_until=candidate.valid_until,
            status=MemoryStatus.ACTIVE,
            supersedes_memory_id=superseded_memory_id,
            metadata={
                **candidate.metadata,
                "explicit_request": candidate.explicit_request,
                "operation": candidate.operation.value,
                "assertion_type": "explicit" if candidate.explicit_request else "extracted",
            },
        )

        stored = self._repository.insert(new_memory)
        self._repository.rebuild_memory_index()

        return stored

    def retrieve(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        query: str,
        limit: int = 12,
    ) -> list[MemoryRecord]:
        memories = self._repository.list_active(
            user_id=user_id,
            intelligence_id=intelligence_id,
        )

        selected = self._retriever.retrieve(
            query=query,
            memories=memories,
            limit=limit,
        )

        for memory in selected:
            self._repository.record_access(memory)

        return selected

    def build_context(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        query: str,
        token_budget: int = 1500,
        limit: int = 12,
    ) -> str:
        memories = self.retrieve(
            user_id=user_id,
            intelligence_id=intelligence_id,
            query=query,
            limit=limit,
        )

        return self._context_builder.build(
            memories=memories,
            token_budget=token_budget,
        )

    def list_memories(
        self,
        *,
        user_id: str,
        intelligence_id: str,
    ) -> list[MemoryRecord]:
        return self._repository.list_active(
            user_id=user_id,
            intelligence_id=intelligence_id,
        )

    def forget(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        memory_id: str,
    ) -> None:
        memory = self._repository.get(
            user_id=user_id,
            intelligence_id=intelligence_id,
            memory_id=memory_id,
        )

        if memory is None:
            raise MemoryNotFoundError(memory_id)

        self._repository.mark_deleted(memory)
        self._repository.rebuild_memory_index()

    def forget_matching(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        namespace: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
        value: Any | None = None,
    ) -> int:
        memories = self._repository.list_active(
            user_id=user_id,
            intelligence_id=intelligence_id,
            namespace=namespace,
        )

        deleted_count = 0

        for memory in memories:
            if subject and memory.subject != subject:
                continue

            if predicate and memory.predicate != predicate:
                continue

            if value is not None and not self._values_equivalent(memory.value, value):
                continue

            self._repository.mark_deleted(memory)
            deleted_count += 1

        if deleted_count:
            self._repository.rebuild_memory_index()

        return deleted_count

    @classmethod
    def _find_equivalent(
        cls,
        memories: list[MemoryRecord],
        value: Any,
    ) -> MemoryRecord | None:
        for memory in memories:
            if cls._values_equivalent(memory.value, value):
                return memory

        return None

    @staticmethod
    def _values_equivalent(first: Any, second: Any) -> bool:
        return json.dumps(
            first,
            sort_keys=True,
            separators=(",", ":"),
        ) == json.dumps(
            second,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _hash_source(source_text: str) -> str | None:
        if not source_text:
            return None

        return hashlib.sha256(source_text.encode("utf-8")).hexdigest()
