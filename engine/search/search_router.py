from __future__ import annotations

import os
from typing import Any

from engine.search.page_search import search_crawled_pages
from engine.search.query_rewriter import rewrite_query
from engine.search.providers.openai_provider import search_openai
from engine.search.providers.brave_provider import search_brave
from engine.search.providers.bing_provider import search_bing


SearchResult = dict[str, Any]


def get_search_provider() -> str:
    provider = os.getenv("PAIGE_SEARCH_PROVIDER", "openai").strip().lower()

    if provider not in {"openai", "brave", "bing"}:
        return "openai"

    return provider


def local_result_is_relevant(results: list[SearchResult]) -> bool:
    if not results:
        return False

    first = results[0]

    if first.get("provider") != "local_crawled_pages":
        return False

    score = int(first.get("score", 0))
    matched_terms = first.get("matched_terms", [])

    return score >= 5 and bool(matched_terms)


def external_provider_search(query: str, limit: int) -> list[SearchResult]:
    provider = get_search_provider()

    if provider == "brave":
        return search_brave(query, limit=limit)

    if provider == "bing":
        return search_bing(query, limit=limit)

    return search_openai(query, limit=limit)


def search_web(
    query: str,
    limit: int = 5,
    chat_history: list[str] | None = None,
) -> list[SearchResult]:
    clean_query = query.strip()

    if not clean_query:
        return []

    optimized_query = rewrite_query(clean_query, chat_history=chat_history)
    local_results = search_crawled_pages(optimized_query, limit=limit)

    if local_result_is_relevant(local_results):
        return local_results

    return external_provider_search(optimized_query, limit=limit)
