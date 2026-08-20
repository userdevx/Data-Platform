from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRAWLED_PAGES_FILE = PROJECT_ROOT / "data" / "pages" / "crawled_pages.jsonl"

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "that", "the", "this", "to", "was", "what", "when", "where",
    "which", "who", "why", "with", "make",
}


def tokenize(value: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", value.lower())

    return [
        word
        for word in words
        if word not in STOP_WORDS and len(word) > 2
    ]


def load_crawled_pages() -> list[dict[str, Any]]:
    if not CRAWLED_PAGES_FILE.exists():
        return []

    pages: list[dict[str, Any]] = []

    with CRAWLED_PAGES_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            try:
                pages.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return pages


def search_crawled_pages(query: str, limit: int = 5) -> list[dict[str, Any]]:
    query_terms = set(tokenize(query))

    if not query_terms:
        return []

    ranked_results: list[dict[str, Any]] = []

    for page in load_crawled_pages():
        metadata = page.get("metadata", {})
        title = metadata.get("title", "")
        url = metadata.get("url", page.get("value", ""))
        headings = " ".join(metadata.get("headings", []))
        text = metadata.get("text", "")

        title_terms = set(tokenize(title))
        heading_terms = set(tokenize(headings))
        text_terms = set(tokenize(text))

        title_matches = query_terms.intersection(title_terms)
        heading_matches = query_terms.intersection(heading_terms)
        text_matches = query_terms.intersection(text_terms)

        matched_terms = title_matches.union(heading_matches).union(text_matches)

        if not matched_terms:
            continue

        required_ratio = 1.0 if len(query_terms) <= 2 else 0.5
        match_ratio = len(matched_terms) / len(query_terms)

        if match_ratio < required_ratio:
            continue

        score = 0
        score += len(title_matches) * 10
        score += len(heading_matches) * 5
        score += len(text_matches) * 1

        if score < 2:
            continue

        ranked_results.append(
            {
                "title": title or "Untitled Page",
                "url": url,
                "source_excerpt": text[:500],
                "provider": "local_crawled_pages",
                "score": score,
                "matched_terms": sorted(matched_terms),
            }
        )

    ranked_results.sort(key=lambda item: item["score"], reverse=True)

    return ranked_results[:limit]
