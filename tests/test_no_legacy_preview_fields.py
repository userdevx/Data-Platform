from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SEARCH_ROOTS = (
    PROJECT_ROOT / "application" / "data-platform-app" / "src",
    PROJECT_ROOT / "application" / "data-platform-app" / "src-tauri" / "src",
    PROJECT_ROOT / "engine",
    PROJECT_ROOT / "config",
    PROJECT_ROOT / "tests",
)

ACTIVE_SUFFIXES = {
    ".py",
    ".rs",
    ".ts",
    ".tsx",
    ".json",
    ".toml",
    ".html",
    ".css",
}

EXCLUDED_PARTS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "__pycache__",
    "data",
}

LEGACY_TERMS = (
    "sni" + "ppet",
    "content_" + "preview",
)


def active_source_files():
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix not in ACTIVE_SUFFIXES:
                continue

            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue

            if ".backup" in path.name:
                continue

            yield path


def test_active_code_contains_no_legacy_preview_fields():
    violations: list[str] = []

    for path in active_source_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()

            if any(term in lowered for term in LEGACY_TERMS):
                relative_path = path.relative_to(PROJECT_ROOT)
                violations.append(
                    f"{relative_path}:{line_number}: {line.strip()}"
                )

    assert not violations, (
        "Legacy preview fields remain in active code:\n"
        + "\n".join(violations)
    )
