from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def read_jsonl(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records[-limit:]


def collect_local_records(limit: int = 200) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    possible_files = [
        DATA_DIR / "records.jsonl",
        DATA_DIR / "records.json",
        DATA_DIR / "paige" / "tasks.jsonl",
        DATA_DIR / "pages" / "crawled_pages.jsonl",
    ]

    for path in possible_files:
        if path.suffix == ".jsonl":
            records.extend(read_jsonl(path, limit=limit))
        elif path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    records.extend(data[-limit:])
                elif isinstance(data, dict):
                    records.append(data)
            except json.JSONDecodeError:
                continue

    return records[-limit:]


def search_local_records(question: str, limit: int = 20) -> list[dict[str, Any]]:
    query_terms = {
        term.lower()
        for term in question.replace("?", "").replace(",", "").split()
        if len(term) > 2
    }

    if not query_terms:
        return []

    matches: list[tuple[int, dict[str, Any]]] = []

    for record in collect_local_records():
        record_text = json.dumps(record, default=str).lower()
        score = sum(1 for term in query_terms if term in record_text)

        if score > 0:
            matches.append((score, record))

    matches.sort(key=lambda item: item[0], reverse=True)

    return [record for _, record in matches[:limit]]
