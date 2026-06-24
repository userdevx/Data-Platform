from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KnowledgePage:
    id: str
    title: str
    content: str
    category: str
    tags: list[str]
    links: list[str]
    backlinks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_knowledge_page(
    title: str,
    content: str,
    category: str = "knowledge",
    tags: list[str] | None = None,
    links: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> KnowledgePage:
    return KnowledgePage(
        id=str(uuid4()),
        title=title.strip(),
        content=content.strip(),
        category=category.strip(),
        tags=tags or [],
        links=links or [],
        metadata=metadata or {},
    )
