from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.data_engine.facade import DataEngineFacade
from engine.memory.context_builder import MemoryContextBuilder
from engine.memory.extraction import RuleBasedMemoryExtractor
from engine.memory.models import MemoryOperation
from engine.memory.repository import MemoryRepository
from engine.memory.retrieval import MemoryRetriever
from engine.memory.service import MemoryRejectedError, MemoryService
from engine.memory.validation import MemoryValidator


def build_memory_service(root: Path) -> MemoryService:
    data_engine = DataEngineFacade(root=root).connect()

    return MemoryService(
        repository=MemoryRepository(data_engine),
        validator=MemoryValidator(),
        retriever=MemoryRetriever(),
        context_builder=MemoryContextBuilder(),
    )


def get_user_id() -> str:
    return os.environ.get("DATA_PLATFORM_USER_ID", "local_user")


def get_definition_value(definition: Any, *path: str, default: Any = None) -> Any:
    current = definition

    for key in path:
        if isinstance(current, dict):
            current = current.get(key, default)
            continue

        current = getattr(current, key, default)

    return current


def get_intelligence_id(definition: Any) -> str:
    return (
        get_definition_value(definition, "identity", "id")
        or get_definition_value(definition, "identity", "name")
        or get_definition_value(definition, "intelligence_id")
        or get_definition_value(definition, "id")
        or "default"
    )


def is_memory_enabled(definition: Any) -> bool:
    memory_enabled = get_definition_value(
        definition,
        "memory",
        "enabled",
        default=None,
    )

    if memory_enabled is not None:
        return bool(memory_enabled)

    memory_enabled = get_definition_value(
        definition,
        "memory_enabled",
        default=None,
    )

    if memory_enabled is not None:
        return bool(memory_enabled)

    return True


def is_explicit_memory_command(text: str) -> bool:
    normalized = text.lower().strip()

    phrases = [
        "remember that",
        "remember this",
        "save this",
        "store this",
        "add this to memory",
        "from now on",
        "going forward",
        "forget that",
        "forget this",
        "remove this memory",
        "delete this memory",
        "do not remember",
        "what do you remember",
        "list memory",
        "list memories",
        "memory status",
        "show memory",
        "show memories",
    ]

    return any(phrase in normalized for phrase in phrases)


def store_memory_candidates_from_definition(
    *,
    root: Path,
    definition: Any,
    user_text: str,
    source: str,
) -> dict[str, Any]:
    if not is_memory_enabled(definition):
        return {
            "memory_enabled": False,
            "created": 0,
            "deleted": 0,
            "rejected": [],
        }

    service = build_memory_service(root)
    extractor = RuleBasedMemoryExtractor()

    user_id = get_user_id()
    intelligence_id = get_intelligence_id(definition)

    conversation_id = os.environ.get(
        "DATA_PLATFORM_CONVERSATION_ID",
        "local_conversation",
    )
    message_id = f"{source}_{uuid4().hex}"

    candidates = extractor.extract(
        user_id=user_id,
        intelligence_id=intelligence_id,
        conversation_id=conversation_id,
        message_id=message_id,
        text=user_text,
    )

    created = 0
    deleted = 0
    rejected: list[str] = []

    for candidate in candidates:
        try:
            if candidate.operation is MemoryOperation.RETRACT:
                deleted += service.forget_matching(
                    user_id=candidate.user_id,
                    intelligence_id=candidate.intelligence_id,
                    namespace=candidate.namespace,
                    subject=candidate.subject,
                    predicate=candidate.predicate,
                    value=candidate.value,
                )
                continue

            memory = service.remember(candidate)

            if memory is not None:
                created += 1

        except MemoryRejectedError as error:
            rejected.append(str(error))

    return {
        "memory_enabled": True,
        "created": created,
        "deleted": deleted,
        "rejected": rejected,
    }


def list_memory_records_from_definition(
    *,
    root: Path,
    definition: Any,
) -> list[dict[str, Any]]:
    if not is_memory_enabled(definition):
        return []

    service = build_memory_service(root)

    memories = service.list_memories(
        user_id=get_user_id(),
        intelligence_id=get_intelligence_id(definition),
    )

    return [
        {
            "memory_id": str(memory.memory_id),
            "namespace": memory.namespace,
            "kind": memory.kind.value,
            "subject": memory.subject,
            "predicate": memory.predicate,
            "value": memory.value,
            "canonical_text": memory.canonical_text,
            "confidence": memory.confidence,
            "importance": memory.importance,
            "status": memory.status.value,
            "updated_at": memory.updated_at.isoformat(),
        }
        for memory in memories
    ]


def process_memory_command_from_definition(
    *,
    root: Path,
    definition: Any,
    user_text: str,
    source: str,
) -> dict[str, Any]:
    normalized = user_text.lower().strip()

    if any(
        phrase in normalized
        for phrase in [
            "what do you remember",
            "list memory",
            "list memories",
            "memory status",
            "show memory",
            "show memories",
        ]
    ):
        memories = list_memory_records_from_definition(
            root=root,
            definition=definition,
        )

        return {
            "mode": "list",
            "created": 0,
            "deleted": 0,
            "rejected": [],
            "memories": memories,
        }

    result = store_memory_candidates_from_definition(
        root=root,
        definition=definition,
        user_text=user_text,
        source=source,
    )

    return {
        "mode": "write",
        "created": result.get("created", 0),
        "deleted": result.get("deleted", 0),
        "rejected": result.get("rejected", []),
        "memories": [],
    }


def build_memory_context_for_provider(
    *,
    root: Path,
    definition: Any,
    question: str,
) -> str:
    if not is_memory_enabled(definition):
        return ""

    service = build_memory_service(root)

    return service.build_context(
        user_id=get_user_id(),
        intelligence_id=get_intelligence_id(definition),
        query=question,
        token_budget=1500,
        limit=12,
    )
