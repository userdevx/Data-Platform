from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.knowledge.page_model import create_knowledge_page
from engine.knowledge.wiki_links import extract_wiki_links


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"
PAGES_FILE = KNOWLEDGE_DIR / "pages.jsonl"


def read_pages() -> list[dict[str, Any]]:
    if not PAGES_FILE.exists():
        return []

    pages: list[dict[str, Any]] = []

    with PAGES_FILE.open("r", encoding="utf-8") as file:
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


def write_pages(pages: list[dict[str, Any]]) -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    with PAGES_FILE.open("w", encoding="utf-8") as file:
        for page in pages:
            file.write(json.dumps(page, ensure_ascii=False) + "\n")


def rebuild_backlinks(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    title_map = {page.get("title", ""): page for page in pages}

    for page in pages:
        page["backlinks"] = []

    for page in pages:
        source_title = page.get("title", "")

        for linked_title in page.get("links", []):
            target = title_map.get(linked_title)

            if target is not None and source_title not in target["backlinks"]:
                target["backlinks"].append(source_title)

    return pages


def save_page(
    title: str,
    content: str,
    category: str = "knowledge",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pages = read_pages()
    links = extract_wiki_links(content)

    page = create_knowledge_page(
        title=title,
        content=content,
        category=category,
        tags=tags,
        links=links,
        metadata=metadata,
    ).to_dict()

    pages.append(page)
    pages = rebuild_backlinks(pages)
    write_pages(pages)

    return page


def search_pages(query: str, limit: int = 10) -> list[dict[str, Any]]:
    terms = [
        term.lower()
        for term in query.replace("?", "").replace(",", "").split()
        if len(term) > 2
    ]

    if not terms:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []

    for page in read_pages():
        page_text = json.dumps(page, default=str).lower()
        score = sum(1 for term in terms if term in page_text)

        if score > 0:
            scored.append((score, page))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [page for _, page in scored[:limit]]
