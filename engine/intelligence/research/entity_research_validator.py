from __future__ import annotations

from typing import Any


MINIMUM_CONFIRMED_CONFIDENCE = 0.75
MINIMUM_RESEARCH_SOURCES = 2

UNRETRIEVED_SOURCE_MESSAGE = (
    "The source was discovered, but its content could not be retrieved. "
    "It was not used as evidence."
)

VAGUE_PHRASES = (
    "seems to be",
    "it is possible",
    "probably",
    "may be one of",
    "appears to possibly",
)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def validate_research_source(
    source: Any,
) -> list[str]:
    errors: list[str] = []

    if not isinstance(source, dict):
        return ["A reviewed source must be an object."]

    title = _clean_text(source.get("title"))
    url = _clean_text(source.get("url"))
    source_type = _clean_text(source.get("source_type"))
    retrieved_at = _clean_text(source.get("retrieved_at"))
    retrieved_text = _clean_text(source.get("retrieved_text"))
    source_excerpt = _clean_text(source.get("source_excerpt"))

    if not title:
        errors.append("A reviewed source must include a title.")

    if not url:
        errors.append("A reviewed source must include a URL.")

    if not source_type:
        errors.append("A reviewed source must include a source type.")

    if not retrieved_at:
        errors.append(
            "A reviewed source must include its retrieval time."
        )

    if not retrieved_text and not source_excerpt:
        errors.append(
            "A reviewed source must contain retrieved text "
            "or an exact source excerpt."
        )

    if (
        retrieved_text
        and source_excerpt
        and source_excerpt not in retrieved_text
    ):
        errors.append(
            "The source excerpt must be an exact passage "
            "contained in the retrieved text."
        )

    return errors


def validate_entity_research(
    result: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    sources = result.get("sources_reviewed", [])
    facts = result.get("confirmed_facts", [])
    limitations = result.get("limitations", [])
    unretrieved_sources = result.get("unretrieved_sources", [])
    summary = _clean_text(result.get("summary"))
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

    if not isinstance(unretrieved_sources, list):
        errors.append("unretrieved_sources must be a list.")

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

    valid_reviewed_urls: set[str] = set()

    for index, source in enumerate(sources, start=1):
        source_errors = validate_research_source(source)

        for source_error in source_errors:
            errors.append(
                f"Reviewed source {index}: {source_error}"
            )

        if not source_errors and isinstance(source, dict):
            source_url = _clean_text(source.get("url"))

            if source_url:
                valid_reviewed_urls.add(source_url)

    for index, fact in enumerate(facts, start=1):
        if not isinstance(fact, dict):
            errors.append(
                f"Confirmed fact {index} must be an object."
            )
            continue

        fact_text = _clean_text(fact.get("text"))
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
            source_urls = []

        normalized_source_urls = {
            _clean_text(source_url)
            for source_url in source_urls
            if _clean_text(source_url)
        }

        for source_url in sorted(normalized_source_urls):
            if source_url not in valid_reviewed_urls:
                errors.append(
                    "Fact references a source that was not successfully "
                    f"reviewed: {source_url}"
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
