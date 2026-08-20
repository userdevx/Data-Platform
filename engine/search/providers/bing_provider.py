from __future__ import annotations

from typing import Any


SearchResult = dict[str, Any]


def search_bing(query: str, limit: int = 5) -> list[SearchResult]:
    return [
        {
            "title": "Bing search provider ready",
            "url": "",
            "retrieved_text": "",
            "source_excerpt": "",
            "provider": "bing",
            "query": query,
            "rank": 1,
        }
    ][:limit]
