from uuid import uuid4

import pytest

from engine.market_intelligence.models import (
    PublicContentRecord,
)
from engine.market_intelligence.normalization import (
    normalize_public_content,
    normalize_retrieved_text,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_record(
    text: str,
) -> PublicContentRecord:
    return PublicContentRecord.create(
        source_name=runtime_value(
            "source"
        ),
        source_type=runtime_value(
            "type"
        ),
        retrieved_text=text,
    )


def test_surrounding_whitespace_is_removed():
    value = runtime_value(
        "text"
    )

    assert (
        normalize_retrieved_text(
            f"   {value}   "
        )
        == value
    )


def test_internal_whitespace_is_collapsed():
    first = runtime_value(
        "first"
    )

    second = runtime_value(
        "second"
    )

    normalized = (
        normalize_retrieved_text(
            f"{first}\n\n\t{second}"
        )
    )

    assert normalized == (
        f"{first} {second}"
    )


def test_capitalization_is_preserved():
    value = runtime_value(
        "MixedCase"
    )

    assert (
        normalize_retrieved_text(
            value
        )
        == value
    )


def test_punctuation_is_preserved():
    value = runtime_value(
        "text"
    )

    text = f"{value}: value!"

    assert (
        normalize_retrieved_text(
            text
        )
        == text
    )


def test_record_text_is_normalized():
    value = runtime_value(
        "text"
    )

    record = create_record(
        f"  {value}\n\n"
    )

    result = (
        normalize_public_content(
            record
        )
    )

    assert result is record

    assert (
        record.retrieved_text
        == value
    )


def test_non_string_text_is_rejected():
    with pytest.raises(
        TypeError
    ):
        normalize_retrieved_text(
            1
        )
