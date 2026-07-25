from __future__ import annotations

from typing import Any


MINIMUM_CONFIRMED_CONFIDENCE = 0.75
MINIMUM_RESEARCH_SOURCES = 2

VAGUE_PHRASES = (
    "seems to be",
    "it is possible",
    "probably",
    "may be one of",
    "appears to possibly",
)


def validate_entity_research(
    result: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    sources = result.get("sources_reviewed", [])
    facts = result.get("confirmed_facts", [])
    limitations = result.get("limitations", [])
    summary = str(result.get("summary", "")).strip()
    source_count = result.get("source_count", 0)

    if not isinstance(sources, list):
        errors.append("sources_reviewed must be a list.")
        sources = []

    if not isinstance(facts, list):
        errors.append("confirmed_facts must be a list.")
        facts = []

    if not isinstance(limitations, list):
        errors.append("limitations must be a list.")
        limitations = []

    if not isinstance(source_count, int):
        errors.append("source_count must be an integer.")
    elif source_count != len(sources):
        errors.append(
            "source_count does not match the number of reviewed sources."
        )

    if len(sources) < MINIMUM_RESEARCH_SOURCES:
        errors.append(
            "Entity research requires at least two reviewed sources."
        )

    if not summary:
        errors.append("Research summary is missing.")

    for index, fact in enumerate(facts, start=1):
        if not isinstance(fact, dict):
            errors.append(
                f"Confirmed fact {index} must be an object."
            )
            continue

        fact_text = str(fact.get("text", "")).strip()
        source_urls = fact.get("source_urls", [])
        confidence = fact.get("confidence", 0.0)

        if not fact_text:
            errors.append(
                f"Confirmed fact {index} is missing text."
            )

        if not isinstance(source_urls, list) or not source_urls:
            errors.append(
                f"Fact has no supporting source: {fact_text}"
            )

        if not isinstance(confidence, (int, float)):
            errors.append(
                f"Fact has an invalid confidence value: {fact_text}"
            )
        elif confidence < MINIMUM_CONFIRMED_CONFIDENCE:
            errors.append(
                "Confirmed fact has insufficient confidence: "
                f"{fact_text}"
            )

    lowered_summary = summary.lower()

    for phrase in VAGUE_PHRASES:
        if phrase in lowered_summary and not limitations:
            errors.append(
                "Unsupported uncertainty phrase detected: "
                f"{phrase}"
            )

    return errors
