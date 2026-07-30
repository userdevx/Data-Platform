from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VISION_ROOT = (
    PROJECT_ROOT
    / "engine"
    / "intelligence"
    / "vision"
)

SUSPICIOUS_ASSIGNMENT_TERMS = (
    "object_catalog",
    "action_catalog",
    "scene_catalog",
    "event_catalog",
    "visual_taxonomy",
    "fixed_labels",
    "allowed_labels",
    "known_labels",
)

MAX_CONSTANT_STRING_COLLECTION = 12


def _assignment_names(
    node: ast.AST,
) -> tuple[str, ...]:
    if isinstance(node, ast.Assign):
        names: list[str] = []

        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)

        return tuple(names)

    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    ):
        return (node.target.id,)

    return ()


def _constant_string_collection_size(
    node: ast.AST,
) -> int:
    if not isinstance(
        node,
        (ast.List, ast.Tuple, ast.Set),
    ):
        return 0

    if not node.elts:
        return 0

    if not all(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        for item in node.elts
    ):
        return 0

    return len(node.elts)


def test_no_suspicious_fixed_taxonomy_assignments() -> None:
    violations: list[str] = []

    for path in VISION_ROOT.rglob("*.py"):
        tree = ast.parse(
            path.read_text(encoding="utf-8")
        )

        for node in ast.walk(tree):
            for name in _assignment_names(node):
                normalized = name.casefold()

                if any(
                    term in normalized
                    for term in SUSPICIOUS_ASSIGNMENT_TERMS
                ):
                    relative = path.relative_to(
                        PROJECT_ROOT
                    )
                    violations.append(
                        f"{relative}:{node.lineno}: {name}"
                    )

    assert not violations, "\n".join(violations)


def test_no_large_constant_visual_collections() -> None:
    violations: list[str] = []

    for path in VISION_ROOT.rglob("*.py"):
        tree = ast.parse(
            path.read_text(encoding="utf-8")
        )

        for node in ast.walk(tree):
            size = (
                _constant_string_collection_size(
                    node
                )
            )

            if size > MAX_CONSTANT_STRING_COLLECTION:
                relative = path.relative_to(
                    PROJECT_ROOT
                )
                violations.append(
                    f"{relative}:{node.lineno}: "
                    f"{size} constant strings"
                )

    assert not violations, "\n".join(violations)


def test_no_visual_domain_enums() -> None:
    violations: list[str] = []

    for path in VISION_ROOT.rglob("*.py"):
        tree = ast.parse(
            path.read_text(encoding="utf-8")
        )

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            base_names = {
                base.id
                for base in node.bases
                if isinstance(base, ast.Name)
            }

            if "Enum" not in base_names:
                continue

            relative = path.relative_to(
                PROJECT_ROOT
            )
            violations.append(
                f"{relative}:{node.lineno}: "
                f"{node.name}"
            )

    assert not violations, "\n".join(violations)
