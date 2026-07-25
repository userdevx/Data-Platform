from datetime import datetime, timezone
from uuid import uuid4

from engine.intelligence.research.entity_research_service import (
    EntityResearchService,
)


class FakeSearcher:
    def __init__(
        self,
        result_total: int,
    ) -> None:
        self.result_total = result_total

    def search(
        self,
        query: str,
        source: str,
        requested_output: str,
        limit: int,
    ) -> dict:
        results = []

        for _ in range(self.result_total):
            token = uuid4().hex
            results.append(
                {
                    "title": f"Source {token}",
                    "url": (
                        f"https://{token}.invalid/document"
                    ),
                    "source": "test_index",
                    "score": 10,
                }
            )

        return {
            "status": "success",
            "query": query,
            "target_source": source,
            "requested_output": requested_output,
            "search_query": f'"{query}"',
            "attempted_queries": [
                f'"{query}"',
                f'"{query}" biography',
            ],
            "results": results[:limit],
            "search_provider": "test_index",
            "search_method": "test_lookup",
            "error": "",
        }


def successful_page_reader(
    url: str,
    title: str,
) -> dict:
    token = uuid4().hex
    content = (
        f"Document opening {token}. "
        f"{title} contains exact accessible source content. "
        f"Document closing {token}."
    )

    return {
        "title": title,
        "url": url,
        "content": content,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def test_research_retrieves_multiple_exact_sources() -> None:
    token = uuid4().hex
    entity_name = f"entity_{token}"

    service = EntityResearchService(
        searcher=FakeSearcher(result_total=3),
        page_reader=successful_page_reader,
    )

    result = service.research(
        query=entity_name,
        source="web",
        limit=3,
    )

    research = result["research"]

    assert result["status"] == "success"
    assert research["source_count"] == 3
    assert len(research["sources_reviewed"]) == 3

    for source in research["sources_reviewed"]:
        assert source["retrieved_text"]
        assert source["source_excerpt"]
        assert (
            source["source_excerpt"]
            in source["retrieved_text"]
        )


def test_unretrieved_source_is_not_used_as_evidence() -> None:
    call_count = 0

    def mixed_page_reader(
        url: str,
        title: str,
    ) -> dict:
        nonlocal call_count
        call_count += 1

        if call_count > 1:
            raise RuntimeError(
                "Source access was blocked."
            )

        return successful_page_reader(
            url,
            title,
        )

    service = EntityResearchService(
        searcher=FakeSearcher(result_total=2),
        page_reader=mixed_page_reader,
    )

    result = service.research(
        query=f"entity_{uuid4().hex}",
        source="web",
        limit=2,
    )

    research = result["research"]

    assert result["status"] == "insufficient_evidence"
    assert research["source_count"] == 1
    assert len(research["unretrieved_sources"]) == 1
    assert len(research["sources_reviewed"]) == 1
