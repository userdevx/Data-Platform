from __future__ import annotations

from typing import Any, TypedDict


class ResearchSource(TypedDict):
    title: str
    url: str
    platform: str | None
    source_type: str
    retrieved_text: str
    source_excerpt: str
    retrieved_at: str


class UnretrievedSource(TypedDict):
    title: str
    url: str
    source_type: str
    reason: str
    discovered_at: str


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
    unretrieved_sources: list[UnretrievedSource]
    source_count: int
    searches_performed: list[str]
    limitations: list[str]
    confidence: float
    status: str
