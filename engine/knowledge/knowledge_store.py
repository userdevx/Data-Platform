from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from engine.knowledge.page_model import create_knowledge_page
from engine.knowledge.wiki_links import extract_wiki_links


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"
PAGES_FILE = KNOWLEDGE_DIR / "pages.jsonl"


_SEARCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "could",
    "define",
    "describe",
    "do",
    "does",
    "explain",
    "for",
    "from",
    "give",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "please",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
}


def _tokens(value: Any) -> list[str]:
    text = str(value or "").lower()

    return re.findall(
        r"[a-z0-9]+(?:'[a-z0-9]+)?",
        text,
    )


def _meaningful_terms(
    query: str,
) -> list[str]:
    terms: list[str] = []

    for token in _tokens(query):
        if len(token) <= 1:
            continue

        if token in _SEARCH_STOP_WORDS:
            continue

        if token not in terms:
            terms.append(token)

    return terms


def _normalized_phrase(
    value: Any,
) -> str:
    return " ".join(
        _tokens(value)
    )


def _score_page(
    page: dict[str, Any],
    terms: list[str],
) -> int:
    if not terms:
        return 0

    title = page.get(
        "title",
        "",
    )

    category = page.get(
        "category",
        "",
    )

    tags = page.get(
        "tags",
        [],
    )

    content = page.get(
        "content",
        "",
    )

    title_tokens = set(
        _tokens(title)
    )

    category_tokens = set(
        _tokens(category)
    )

    content_tokens = set(
        _tokens(content)
    )

    tag_tokens: set[str] = set()

    if isinstance(tags, list):
        for tag in tags:
            tag_tokens.update(
                _tokens(tag)
            )

    query_phrase = " ".join(
        terms
    )

    title_phrase = _normalized_phrase(
        title
    )

    score = 0

    # Exact title representation is the strongest evidence.
    if (
        query_phrase
        and title_phrase == query_phrase
    ):
        score += 100

    elif (
        query_phrase
        and query_phrase in title_phrase
    ):
        score += 50

    # Field-specific weighting.
    for term in terms:
        if term in title_tokens:
            score += 12

        if term in tag_tokens:
            score += 8

        if term in category_tokens:
            score += 4

        if term in content_tokens:
            score += 1

    return score


def read_pages() -> list[dict[str, Any]]:
    if not PAGES_FILE.exists():
        return []

    pages: list[dict[str, Any]] = []

    with PAGES_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            if not line.strip():
                continue

            try:
                page = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(page, dict):
                pages.append(page)

    return pages


def write_pages(
    pages: list[dict[str, Any]],
) -> None:
    KNOWLEDGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with PAGES_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        for page in pages:
            file.write(
                json.dumps(
                    page,
                    ensure_ascii=False,
                )
                + "\n"
            )


def rebuild_backlinks(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    title_map = {
        page.get("title", ""): page
        for page in pages
    }

    for page in pages:
        page["backlinks"] = []

    for page in pages:
        source_title = page.get(
            "title",
            "",
        )

        for linked_title in page.get(
            "links",
            [],
        ):
            target = title_map.get(
                linked_title
            )

            if target is None:
                continue

            if source_title in target["backlinks"]:
                continue

            target["backlinks"].append(
                source_title
            )

    return pages


def save_page(
    title: str,
    content: str,
    category: str = "knowledge",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pages = read_pages()

    links = extract_wiki_links(
        content
    )

    page = create_knowledge_page(
        title=title,
        content=content,
        category=category,
        tags=tags,
        links=links,
        metadata=metadata,
    ).to_dict()

    pages.append(page)

    pages = rebuild_backlinks(
        pages
    )

    write_pages(
        pages
    )

    return page


def search_pages(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    terms = _meaningful_terms(
        query
    )

    if not terms:
        return []

    scored: list[
        tuple[int, str, dict[str, Any]]
    ] = []

    for page in read_pages():
        score = _score_page(
            page=page,
            terms=terms,
        )

        if score <= 0:
            continue

        title = str(
            page.get(
                "title",
                "",
            )
        ).lower()

        scored.append(
            (
                score,
                title,
                page,
            )
        )

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    return [
        page
        for _, _, page
        in scored[:limit]
    ]
