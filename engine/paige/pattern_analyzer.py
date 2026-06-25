from __future__ import annotations

from collections import Counter
from typing import Any


def analyze_patterns(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "record_count": 0,
            "sources": {},
            "categories": {},
            "statuses": {},
            "summary": "No relevant local records were found.",
        }

    sources = Counter()
    categories = Counter()
    statuses = Counter()

    for record in records:
        source = record.get("source")
        category = record.get("category")
        status = record.get("status")

        if source:
            sources[str(source)] += 1

        if category:
            categories[str(category)] += 1

        if status:
            statuses[str(status)] += 1

    return {
        "record_count": len(records),
        "sources": dict(sources.most_common(10)),
        "categories": dict(categories.most_common(10)),
        "statuses": dict(statuses.most_common(10)),
        "summary": f"Found {len(records)} relevant local records.",
    }
