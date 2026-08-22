from __future__ import annotations

import re
import unicodedata

from engine.market_intelligence.models import (
    PublicContentRecord,
)


_WHITESPACE_PATTERN = re.compile(
    r"\s+"
)


def normalize_retrieved_text(
    text: str,
) -> str:
    if not isinstance(
        text,
        str,
    ):
        raise TypeError(
            "Retrieved text must be a string."
        )

    normalized_unicode = (
        unicodedata.normalize(
            "NFC",
            text,
        )
    )

    return _WHITESPACE_PATTERN.sub(
        " ",
        normalized_unicode.strip(),
    )


def normalize_public_content(
    record: PublicContentRecord,
) -> PublicContentRecord:
    record.retrieved_text = (
        normalize_retrieved_text(
            record.retrieved_text
        )
    )

    return record
