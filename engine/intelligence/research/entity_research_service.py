from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from engine.intelligence.research.entity_research_validator import (
    UNRETRIEVED_SOURCE_MESSAGE,
    validate_entity_research,
)
from engine.intelligence.search.public_source_search import (
    PublicSourceSearch,
)
from engine.security.intelligence_safe_executor import (
    run_safe_intelligence_tool,
)


PageReader = Callable[[str, str], dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def select_source_excerpt(
    retrieved_text: str,
    query: str,
    max_characters: int = 1200,
) -> str:
    clean_text = retrieved_text.strip()

    if not clean_text:
        return ""

    normalized_text = clean_text.lower()
    tokens = [
        token.lower()
        for token in query.split()
        if len(token) > 1
    ]

    match_position = 0

    for token in tokens:
        position = normalized_text.find(token)

        if position >= 0:
            match_position = position
            break

    start = max(0, match_position - 240)
    end = min(
        len(clean_text),
        start + max_characters,
    )

    excerpt = clean_text[start:end].strip()

    if excerpt not in clean_text:
        return ""

    return excerpt


def default_page_reader(
    url: str,
    title: str,
) -> dict[str, Any]:
    return run_safe_intelligence_tool(
        tool_name="internet.read_page",
        params={
            "url": url,
            "title": title,
        },
    )


class EntityResearchService:
    def __init__(
        self,
        searcher: PublicSourceSearch | None = None,
        page_reader: PageReader | None = None,
    ) -> None:
        self.searcher = searcher or PublicSourceSearch()
        self.page_reader = (
            page_reader
            or default_page_reader
        )

    def research(
        self,
        query: str,
        source: str = "web",
        limit: int = 5,
    ) -> dict[str, Any]:
        clean_query = " ".join(
            query.split()
        ).strip()
        safe_limit = max(2, min(limit, 8))

        discovery = self.searcher.search(
            query=clean_query,
            source=source,
            requested_output="bio_summary",
            limit=safe_limit * 2,
        )

        discovered_results = discovery.get(
            "results",
            [],
        )

        reviewed_sources: list[dict[str, Any]] = []
        unretrieved_sources: list[dict[str, Any]] = []

        for item in discovered_results:
            if len(reviewed_sources) >= safe_limit:
                break

            title = str(
                item.get("title", "")
            ).strip()
            url = str(
                item.get("url", "")
            ).strip()

            if not url:
                continue

            try:
                page = self.page_reader(
                    url,
                    title,
                )
                retrieved_text = str(
                    page.get("content", "")
                ).strip()

                if not retrieved_text:
                    raise ValueError(
                        "No accessible source content was returned."
                    )

                source_excerpt = select_source_excerpt(
                    retrieved_text=retrieved_text,
                    query=clean_query,
                )

                if not source_excerpt:
                    raise ValueError(
                        "An exact source excerpt could not be selected."
                    )

                final_url = str(
                    page.get("url", url)
                ).strip()
                final_title = str(
                    page.get("title", title)
                ).strip()

                reviewed_sources.append(
                    {
                        "title": final_title or final_url,
                        "url": final_url,
                        "platform": (
                            None
                            if source == "web"
                            else source
                        ),
                        "source_type": (
                            "public_web_page"
                            if source == "web"
                            else "public_profile"
                        ),
                        "retrieved_text": retrieved_text,
                        "source_excerpt": source_excerpt,
                        "retrieved_at": str(
                            page.get(
                                "created_at",
                                utc_now(),
                            )
                        ),
                    }
                )

            except Exception as error:
                unretrieved_sources.append(
                    {
                        "title": title or url,
                        "url": url,
                        "source_type": (
                            "public_web_page"
                            if source == "web"
                            else "public_profile"
                        ),
                        "reason": (
                            f"{UNRETRIEVED_SOURCE_MESSAGE} "
                            f"Reason: {error}"
                        ),
                        "discovered_at": utc_now(),
                    }
                )

        source_count = len(reviewed_sources)

        limitations: list[str] = []

        if unretrieved_sources:
            limitations.append(
                f"{len(unretrieved_sources)} discovered "
                "source(s) could not be retrieved and "
                "were not used as evidence."
            )

        if source_count < 2:
            limitations.append(
                "Fewer than two sources supplied accessible "
                "content, so the result is insufficient for "
                "complete entity research."
            )

        limitations.append(
            "The current stage returns exact source excerpts. "
            "Confirmed claim extraction and cross-source "
            "comparison run in the next research stage."
        )

        summary = (
            f"Exact accessible content was retrieved from "
            f"{source_count} public source(s) for "
            f"{clean_query}."
        )

        research_result: dict[str, Any] = {
            "entity_name": clean_query,
            "summary": summary,
            "confirmed_facts": [],
            "possible_matches": [
                {
                    "title": str(
                        item.get("title", "")
                    ),
                    "url": str(
                        item.get("url", "")
                    ),
                    "source": str(
                        item.get("source", "")
                    ),
                    "score": item.get("score", 0),
                }
                for item in discovered_results
            ],
            "public_profiles": (
                reviewed_sources
                if source != "web"
                else []
            ),
            "sources_reviewed": reviewed_sources,
            "unretrieved_sources": unretrieved_sources,
            "source_count": source_count,
            "searches_performed": discovery.get(
                "attempted_queries",
                [],
            ),
            "limitations": limitations,
            "confidence": self._calculate_confidence(
                source_count
            ),
            "status": (
                "success"
                if source_count >= 2
                else "insufficient_evidence"
            ),
        }

        validation_errors = validate_entity_research(
            research_result
        )

        if validation_errors:
            research_result["status"] = (
                "insufficient_evidence"
            )

            for error in validation_errors:
                if error not in research_result["limitations"]:
                    research_result["limitations"].append(
                        error
                    )

        answer = self._format_answer(
            research_result
        )

        return {
            "status": research_result["status"],
            "answer": answer,
            "query": clean_query,
            "target_source": source,
            "requested_output": "bio_summary",
            "search_query": discovery.get(
                "search_query",
                "",
            ),
            "attempted_queries": discovery.get(
                "attempted_queries",
                [],
            ),
            "search_provider": discovery.get(
                "search_provider",
                "public_web_index",
            ),
            "search_method": (
                "multi_query_source_retrieval"
            ),
            "results": [
                {
                    "title": item["title"],
                    "url": item["url"],
                    "source": item["source_type"],
                    "score": 0,
                }
                for item in reviewed_sources
            ],
            "research": research_result,
            "error": discovery.get("error", ""),
        }

    def _calculate_confidence(
        self,
        source_count: int,
    ) -> float:
        if source_count <= 0:
            return 0.0

        if source_count == 1:
            return 0.45

        if source_count == 2:
            return 0.70

        return min(
            0.90,
            0.70 + ((source_count - 2) * 0.05),
        )

    def _format_answer(
        self,
        result: dict[str, Any],
    ) -> str:
        lines = [
            str(result["entity_name"]),
            "",
            "Summary",
            str(result["summary"]),
        ]

        reviewed_sources = result[
            "sources_reviewed"
        ]

        if reviewed_sources:
            lines.extend(
                [
                    "",
                    "Exact source excerpts",
                ]
            )

            for index, source in enumerate(
                reviewed_sources,
                start=1,
            ):
                lines.extend(
                    [
                        "",
                        f"{index}. {source['title']}",
                        source["source_excerpt"],
                        f"Source: {source['url']}",
                    ]
                )

        lines.extend(
            [
                "",
                "Sources reviewed",
                str(result["source_count"]),
            ]
        )

        limitations = result.get(
            "limitations",
            [],
        )

        if limitations:
            lines.extend(
                [
                    "",
                    "Limitations",
                ]
            )

            for limitation in limitations:
                lines.append(
                    f"- {limitation}"
                )

        lines.extend(
            [
                "",
                "Confidence",
                f"{result['confidence']:.2f}",
            ]
        )

        return "\n".join(lines)
