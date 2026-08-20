from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EvidenceRecord:
    title: str
    url: str
    retrieved_text: str
    source_excerpt: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "EvidenceRecord":
        return cls(
            title=_clean_text(value.get("title")),
            url=_clean_text(value.get("url")),
            retrieved_text=_clean_text(value.get("retrieved_text")),
            source_excerpt=_clean_text(value.get("source_excerpt")),
        )

    @property
    def has_opened_content(self) -> bool:
        return bool(
            self.url
            and self.retrieved_text
            and self.source_excerpt
        )


@dataclass(frozen=True)
class EvidenceDecision:
    allowed: bool
    reason: str
    evidence: tuple[EvidenceRecord, ...]


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return " ".join(value.split())


def _unique_evidence(
    records: Iterable[EvidenceRecord],
) -> tuple[EvidenceRecord, ...]:
    unique: list[EvidenceRecord] = []
    seen: set[tuple[str, str]] = set()

    for record in records:
        key = (record.url.casefold(), record.source_excerpt.casefold())

        if key in seen:
            continue

        seen.add(key)
        unique.append(record)

    return tuple(unique)


def validate_research_evidence(
    raw_records: Iterable[dict[str, Any]],
    *,
    minimum_sources: int = 1,
    minimum_excerpt_length: int = 40,
) -> EvidenceDecision:
    if minimum_sources < 1:
        raise ValueError("minimum_sources must be at least 1")

    parsed = (
        EvidenceRecord.from_mapping(record)
        for record in raw_records
        if isinstance(record, dict)
    )

    usable = _unique_evidence(
        record
        for record in parsed
        if record.has_opened_content
        and len(record.source_excerpt) >= minimum_excerpt_length
        and record.source_excerpt in record.retrieved_text
    )

    if len(usable) < minimum_sources:
        return EvidenceDecision(
            allowed=False,
            reason=(
                "Insufficient opened-source evidence. "
                "The system must retrieve exact source content "
                "before generating a factual answer."
            ),
            evidence=usable,
        )

    return EvidenceDecision(
        allowed=True,
        reason="Evidence requirements satisfied.",
        evidence=usable,
    )


def build_evidence_context(
    decision: EvidenceDecision,
) -> str:
    if not decision.allowed:
        raise ValueError(
            "Evidence context cannot be built from a blocked decision."
        )

    sections: list[str] = []

    for index, record in enumerate(decision.evidence, start=1):
        sections.append(
            "\n".join(
                (
                    f"[Source {index}]",
                    f"Title: {record.title}",
                    f"URL: {record.url}",
                    f"Exact passage: {record.source_excerpt}",
                )
            )
        )

    return "\n\n".join(sections)
