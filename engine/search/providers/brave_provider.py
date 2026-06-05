from __future__ import annotations

from typing import Any


SearchResult = dict[str, Any]


def search_brave(query: str, limit: int = 5) -> list[SearchResult]:
    return [
        {
            "title": "Brave search provider ready",
            "url": "",
            "snippet": (
                "The Brave provider route is connected. "
                "Add BRAVE_SEARCH_API_KEY later to activate live Brave Search."
            ),
            "provider": "brave",
            "query": query,
            "rank": 1,
        }
    ][:limit]
