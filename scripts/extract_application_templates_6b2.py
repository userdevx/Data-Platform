from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "application/data-platform-app/src-tauri/src"
    / "application_generation.rs"
)

DESTINATION = (
    ROOT
    / "engine/application_generation/templates"
    / "_rust_snapshot"
)

FUNCTIONS = {
    "web": "web_application_files",
    "desktop": "desktop_application_files",
    "data": "data_application_files",
    "automation": "automation_tool_files",
}

NEXT_FUNCTION = {
    "web": "desktop_application_files",
    "desktop": "data_application_files",
    "data": "automation_tool_files",
    "automation": "generated_files",
}

RAW_START = re.compile(r'r(#{0,16})"')


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def function_section(
    source: str,
    name: str,
    following: str,
) -> tuple[int, str]:
    start_match = re.search(
        rf"(?m)^fn {re.escape(name)}\s*\(",
        source,
    )
    end_match = re.search(
        rf"(?m)^fn {re.escape(following)}\s*\(",
        source,
    )

    if start_match is None or end_match is None:
        raise RuntimeError(
            f"Function boundary missing: {name}"
        )

    if end_match.start() <= start_match.start():
        raise RuntimeError(
            f"Invalid function ordering: {name}"
        )

    return (
        start_match.start(),
        source[start_match.start():end_match.start()],
    )


def raw_literals(section: str):
    cursor = 0

    while True:
        match = RAW_START.search(section, cursor)

        if match is None:
            return

        hashes = match.group(1)
        closing = '"' + hashes

        start = match.end()
        end = section.find(closing, start)

        if end < 0:
            raise RuntimeError(
                "Unterminated Rust raw string."
            )

        yield (
            match.start(),
            section[start:end],
        )

        cursor = end + len(closing)


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    source = source_bytes.decode("utf-8")

    if DESTINATION.exists():
        raise RuntimeError(
            "STOP: snapshot directory already exists. "
            "Do not overwrite extracted templates."
        )

    extracted = {}
    total = 0

    for category, function in FUNCTIONS.items():
        start, section = function_section(
            source,
            function,
            NEXT_FUNCTION[category],
        )

        entries = []

        for number, (offset, content) in enumerate(
            raw_literals(section),
            start=1,
        ):
            encoded = content.encode("utf-8")

            entries.append({
                "file": f"{category}/raw_{number:02d}.txt",
                "sha256": digest(encoded),
                "size_bytes": len(encoded),
                "source_byte_offset": len(
                    source[:start + offset].encode("utf-8")
                ),
            })

        extracted[category] = {
            "function": function,
            "literals": entries,
        }

        total += len(entries)

    if total == 0:
        raise RuntimeError(
            "No Rust raw-string literals found. "
            "Source inspection is required."
        )

    DESTINATION.mkdir(parents=True, exist_ok=False)

    for category, function in FUNCTIONS.items():
        _, section = function_section(
            source,
            function,
            NEXT_FUNCTION[category],
        )

        values = list(raw_literals(section))
        entries = extracted[category]["literals"]

        for (_, content), entry in zip(values, entries):
            path = DESTINATION / entry["file"]
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            path.write_bytes(content.encode("utf-8"))

            if digest(path.read_bytes()) != entry["sha256"]:
                raise RuntimeError(
                    f"Template verification failed: {path}"
                )

    manifest = {
        "definition_version": 1,
        "purpose": "Rust template source snapshot",
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": digest(source_bytes),
        "categories": extracted,
    }

    (DESTINATION / "snapshot.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("SOURCE_SHA256:", digest(source_bytes))

    for category, details in extracted.items():
        print(
            f"{category}: "
            f"{len(details['literals'])} raw literals"
        )

    print("TOTAL_RAW_LITERALS:", total)
    print("SNAPSHOT:", DESTINATION)
    print("SOURCE_EXTRACTION_PASS")


if __name__ == "__main__":
    main()
