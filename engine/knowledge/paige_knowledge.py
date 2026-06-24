from __future__ import annotations

from typing import Any

from engine.knowledge.knowledge_store import search_pages


def retrieve_second_brain_context(question: str, limit: int = 5) -> list[dict[str, Any]]:
    return search_pages(question, limit=limit)


def format_second_brain_context(pages: list[dict[str, Any]]) -> str:
    if not pages:
        return ""

    lines = ["Second Brain matches:", ""]

    for index, page in enumerate(pages, start=1):
        title = page.get("title", "Untitled")
        category = page.get("category", "knowledge")
        tags = ", ".join(page.get("tags", []))
        content = page.get("content", "")

        preview = content[:300] + "..." if len(content) > 300 else content

        lines.append(f"{index}. {title}")
        lines.append(f"   Category: {category}")
        lines.append(f"   Tags: {tags}")
        lines.append(f"   Preview: {preview}")
        lines.append("")

    return "\n".join(lines)
