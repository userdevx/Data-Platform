from __future__ import annotations

from typing import Any, TypedDict


class ResearchSource(TypedDict):
    title: str
    url: str
    platform: str | None
    source_type: str
    snippet: str
    retrieved_at: str


class ResearchFact(TypedDict):
    text: str
    source_urls: list[str]
    confidence: float
    verification_status: str


class EntityResearchResult(TypedDict):
    entity_name: str
    summary: str
    confirmed_facts: list[ResearchFact]
    possible_matches: list[dict[str, Any]]
    public_profiles: list[ResearchSource]
    sources_reviewed: list[ResearchSource]
    source_count: int
    searches_performed: list[str]
    limitations: list[str]
    confidence: float
    status: str
