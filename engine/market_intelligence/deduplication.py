from __future__ import annotations

import hashlib

from engine.market_intelligence.models import (
    PublicContentRecord,
)
from engine.market_intelligence.normalization import (
    normalize_retrieved_text,
)


def content_fingerprint(
    record: PublicContentRecord,
) -> str:
    normalized_text = (
        normalize_retrieved_text(
            record.retrieved_text
        )
    )

    comparison_text = (
        normalized_text.casefold()
    )

    return hashlib.sha256(
        comparison_text.encode(
            "utf-8"
        )
    ).hexdigest()


def deduplicate_public_content(
    records: list[PublicContentRecord],
) -> list[PublicContentRecord]:
    seen_fingerprints: set[str] = set()

    unique_records: list[
        PublicContentRecord
    ] = []

    for record in records:
        fingerprint = (
            content_fingerprint(
                record
            )
        )

        if (
            fingerprint
            in seen_fingerprints
        ):
            continue

        seen_fingerprints.add(
            fingerprint
        )

        unique_records.append(
            record
        )

    return unique_records
