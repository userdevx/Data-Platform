from __future__ import annotations

import hashlib
import json

from scripts.extract_application_templates_6b2 import (
    DESTINATION,
    FUNCTIONS,
    NEXT_FUNCTION,
    SOURCE,
    function_section,
    raw_literals,
)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_snapshot_matches_original_rust_source():
    manifest = json.loads(
        (DESTINATION / "snapshot.json").read_text(
            encoding="utf-8"
        )
    )

    source_bytes = SOURCE.read_bytes()
    source_text = source_bytes.decode("utf-8")

    assert manifest["source_sha256"] == sha256(
        source_bytes
    )

    assert set(manifest["categories"]) == set(
        FUNCTIONS
    )

    for category, function in FUNCTIONS.items():
        _, section = function_section(
            source_text,
            function,
            NEXT_FUNCTION[category],
        )

        expected = [
            content.encode("utf-8")
            for _, content in raw_literals(section)
        ]

        entries = manifest["categories"][
            category
        ]["literals"]

        assert len(entries) == len(expected)

        for entry, original in zip(
            entries,
            expected,
        ):
            path = DESTINATION / entry["file"]
            stored = path.read_bytes()

            assert stored == original
            assert entry["size_bytes"] == len(stored)
            assert entry["sha256"] == sha256(stored)
