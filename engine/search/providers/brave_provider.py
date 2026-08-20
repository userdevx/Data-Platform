from __future__ import annotations

from typing import Any


SearchResult = dict[str, Any]


def search_brave(query: str, limit: int = 5) -> list[SearchResult]:
    return [
        {
            "title": "Brave search provider ready",
            "url": "",
            "retrieved_text": "",
            "source_excerpt": "",
            "provider": "brave",
            "query": query,
            "rank": 1,
        }
    ][:limit]
