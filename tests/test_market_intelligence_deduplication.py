from uuid import uuid4

from engine.market_intelligence.deduplication import (
    content_fingerprint,
    deduplicate_public_content,
)
from engine.market_intelligence.models import (
    PublicContentRecord,
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


def test_identical_text_has_same_fingerprint():
    text = runtime_value(
        "text"
    )

    first = create_record(
        text
    )

    second = create_record(
        text
    )

    assert (
        content_fingerprint(
            first
        )
        == content_fingerprint(
            second
        )
    )


def test_whitespace_differences_do_not_create_new_fingerprint():
    first_value = runtime_value(
        "first"
    )

    second_value = runtime_value(
        "second"
    )

    first = create_record(
        f"{first_value} {second_value}"
    )

    second = create_record(
        f" {first_value}\n\t{second_value} "
    )

    assert (
        content_fingerprint(
            first
        )
        == content_fingerprint(
            second
        )
    )


def test_case_differences_do_not_create_new_fingerprint():
    value = runtime_value(
        "text"
    )

    first = create_record(
        value.lower()
    )

    second = create_record(
        value.upper()
    )

    assert (
        content_fingerprint(
            first
        )
        == content_fingerprint(
            second
        )
    )


def test_duplicate_records_are_removed():
    value = runtime_value(
        "text"
    )

    first = create_record(
        value
    )

    duplicate = create_record(
        value
    )

    result = (
        deduplicate_public_content(
            [
                first,
                duplicate,
            ]
        )
    )

    assert result == [
        first
    ]


def test_distinct_records_are_preserved():
    first = create_record(
        runtime_value(
            "first"
        )
    )

    second = create_record(
        runtime_value(
            "second"
        )
    )

    result = (
        deduplicate_public_content(
            [
                first,
                second,
            ]
        )
    )

    assert result == [
        first,
        second,
    ]


def test_first_occurrence_is_preserved():
    value = runtime_value(
        "text"
    )

    first = create_record(
        value
    )

    second = create_record(
        value
    )

    third = create_record(
        value
    )

    result = (
        deduplicate_public_content(
            [
                first,
                second,
                third,
            ]
        )
    )

    assert len(result) == 1
    assert result[0] is first
