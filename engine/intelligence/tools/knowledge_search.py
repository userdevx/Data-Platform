from __future__ import annotations

from typing import Any

from engine.knowledge.knowledge_store import search_pages


class SearchKnowledgeTool:
    """
    Approved local knowledge retrieval tool.

    The tool delegates retrieval to the existing knowledge store.
    It does not access model providers or external networks.
    """

    name = "search_knowledge"

    def execute(
        self,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del context

        query = str(
            arguments.get("query", "")
        ).strip()

        if not query:
            return {
                "query": "",
                "count": 0,
                "results": [],
            }

        raw_limit = arguments.get(
            "limit",
            5,
        )

        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 5

        limit = max(
            1,
            min(limit, 20),
        )

        results = search_pages(
            query=query,
            limit=limit,
        )

        return {
            "query": query,
            "count": len(results),
            "results": results,
        }
