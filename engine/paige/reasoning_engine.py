from __future__ import annotations

import json
from typing import Any

from engine.paige.local_retriever import search_local_records
from engine.paige.pattern_analyzer import analyze_patterns
from engine.paige.query_classifier import classify_query
from engine.search.search_router import search_web
from engine.knowledge.paige_knowledge import retrieve_second_brain_context, format_second_brain_context


def format_local_answer(
    question: str,
    records: list[dict[str, Any]],
    insights: dict[str, Any],
) -> str:
    if not records:
        return ""

    lines = [
        f"Paige analyzed local Data Platform records for: {question}",
        "",
        insights.get("summary", ""),
        "",
    ]

    if insights.get("sources"):
        lines.append("Top sources:")
        for source, count in insights["sources"].items():
            lines.append(f"- {source}: {count}")
        lines.append("")

    if insights.get("categories"):
        lines.append("Top categories:")
        for category, count in insights["categories"].items():
            lines.append(f"- {category}: {count}")
        lines.append("")

    if insights.get("statuses"):
        lines.append("Statuses:")
        for status, count in insights["statuses"].items():
            lines.append(f"- {status}: {count}")
        lines.append("")

    lines.append("Most relevant records:")
    for index, record in enumerate(records[:5], start=1):
        preview = json.dumps(record, default=str)
        if len(preview) > 300:
            preview = preview[:300] + "..."
        lines.append(f"{index}. {preview}")

    return "\n".join(lines)


def ask_paige_reasoning(question: str) -> dict[str, Any]:
    classification = classify_query(question)

    second_brain_pages = retrieve_second_brain_context(question)
    second_brain_context = format_second_brain_context(second_brain_pages)

    if second_brain_context:
        return {
            "route": "second_brain",
            "classification": classification.__dict__,
            "answer": second_brain_context,
            "records_used": len(second_brain_pages),
            "insights": {
                "knowledge_pages_used": len(second_brain_pages)
            },
        }

    if classification.route == "local_reasoning":
        records = search_local_records(question)
        insights = analyze_patterns(records)
        local_answer = format_local_answer(question, records, insights)

        if local_answer:
            return {
                "route": "local_reasoning",
                "classification": classification.__dict__,
                "answer": local_answer,
                "records_used": len(records),
                "insights": insights,
            }

    web_results = search_web(question)

    if web_results:
        first = web_results[0]
        return {
            "route": "web_or_model_answer",
            "classification": classification.__dict__,
            "answer": first.get("snippet", "Paige could not generate an answer."),
            "provider": first.get("provider", "unknown"),
            "records_used": 0,
            "insights": {},
        }

    return {
        "route": "none",
        "classification": classification.__dict__,
        "answer": "Paige could not find enough information to answer this question.",
        "records_used": 0,
        "insights": {},
    }
