from __future__ import annotations

from typing import Any


SearchResult = dict[str, Any]


def search_bing(query: str, limit: int = 5) -> list[SearchResult]:
    return [
        {
            "title": "Bing search provider ready",
            "url": "",
            "snippet": (
                "The Bing provider route is connected. "
                "Add BING_SEARCH_API_KEY later to activate live Bing Search."
            ),
            "provider": "bing",
            "query": query,
            "rank": 1,
        }
    ][:limit]
