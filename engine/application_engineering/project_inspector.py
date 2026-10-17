from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

from engine.application_engineering.models import (
    RepositoryInspection,
)


SOURCE_SUFFIXES = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
}


MANIFEST_NAMES = {
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "tauri.conf.json",
    "requirements.txt",
    "requirements-dev.txt",
}


MAX_SOURCE_FILE_BYTES = (
    2 * 1024 * 1024
)


class ProjectInspectionError(
    RuntimeError
):
    pass


def _require_text(
    value: str,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return normalized


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _read_source_text(
    path: Path,
) -> str | None:
    try:
        size = path.stat().st_size

    except OSError:
        return None

    if size > MAX_SOURCE_FILE_BYTES:
        return None

    try:
        return path.read_text(
            encoding="utf-8"
        )

    except (
        OSError,
        UnicodeDecodeError,
    ):
        return None


def _python_symbols(
    text: str,
) -> tuple[str, ...]:
    try:
        tree = ast.parse(
            text
        )

    except SyntaxError:
        return ()

    symbols: list[str] = []

    for node in tree.body:
        if isinstance(
            node,
            ast.ClassDef,
        ):
            symbols.append(
                f"class {node.name}"
            )

            for child in node.body:
                if isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):
                    symbols.append(
                        (
                            "method "
                            f"{node.name}."
                            f"{child.name}"
                        )
                    )

        elif isinstance(
            node,
            ast.AsyncFunctionDef,
        ):
            symbols.append(
                f"async_function {node.name}"
            )

        elif isinstance(
            node,
            ast.FunctionDef,
        ):
            symbols.append(
                f"function {node.name}"
            )

    return tuple(
        symbols
    )


TYPESCRIPT_SYMBOL_PATTERNS = (
    (
        "class",
        re.compile(
            r"\b(?:export\s+)?class\s+"
            r"([A-Za-z_$][A-Za-z0-9_$]*)"
        ),
    ),
    (
        "interface",
        re.compile(
            r"\b(?:export\s+)?interface\s+"
            r"([A-Za-z_$][A-Za-z0-9_$]*)"
        ),
    ),
    (
        "type",
        re.compile(
            r"\b(?:export\s+)?type\s+"
            r"([A-Za-z_$][A-Za-z0-9_$]*)"
        ),
    ),
    (
        "function",
        re.compile(
            r"\b(?:export\s+)?"
            r"(?:async\s+)?function\s+"
            r"([A-Za-z_$][A-Za-z0-9_$]*)"
        ),
    ),
)


RUST_SYMBOL_PATTERNS = (
    (
        "function",
        re.compile(
            r"\b(?:pub(?:\([^)]*\))?\s+)?"
            r"(?:async\s+)?fn\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
        ),
    ),
    (
        "struct",
        re.compile(
            r"\b(?:pub\s+)?struct\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
        ),
    ),
    (
        "enum",
        re.compile(
            r"\b(?:pub\s+)?enum\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
        ),
    ),
    (
        "trait",
        re.compile(
            r"\b(?:pub\s+)?trait\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
        ),
    ),
)


def _pattern_symbols(
    text: str,
    patterns: Iterable[
        tuple[
            str,
            re.Pattern[str],
        ]
    ],
) -> tuple[str, ...]:
    symbols: list[str] = []

    for symbol_type, pattern in patterns:
        for match in pattern.finditer(
            text
        ):
            symbols.append(
                (
                    f"{symbol_type} "
                    f"{match.group(1)}"
                )
            )

    return tuple(
        dict.fromkeys(
            symbols
        )
    )


def _typescript_symbols(
    text: str,
) -> tuple[str, ...]:
    return _pattern_symbols(
        text,
        TYPESCRIPT_SYMBOL_PATTERNS,
    )


def _rust_symbols(
    text: str,
) -> tuple[str, ...]:
    return _pattern_symbols(
        text,
        RUST_SYMBOL_PATTERNS,
    )


class ProjectInspector:
    """
    Read-only inspection of the live software repository.

    The inspector gathers factual repository state and
    returns the existing RepositoryInspection model.

    It does not:
    - modify files;
    - create Git commits;
    - write Data Engine records;
    - call a model;
    - perform training.
    """

    def __init__(
        self,
        repository_root: str | Path,
    ) -> None:
        supplied_root = Path(
            repository_root
        ).expanduser().resolve()

        if not supplied_root.is_dir():
            raise ProjectInspectionError(
                "Repository root does not exist: "
                f"{supplied_root}"
            )

        self.repository_root = (
            self._resolve_git_root(
                supplied_root
            )
        )

    def _run_git(
        self,
        *arguments: str,
    ) -> str:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(
                    self.repository_root
                ),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            error = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "Git command failed."
            )

            raise ProjectInspectionError(
                error
            )

        return completed.stdout

    @staticmethod
    def _resolve_git_root(
        path: Path,
    ) -> Path:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(
                    path
                ),
                "rev-parse",
                "--show-toplevel",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            raise ProjectInspectionError(
                "Path is not inside a Git repository."
            )

        root_text = completed.stdout.strip()

        if not root_text:
            raise ProjectInspectionError(
                "Git did not return a repository root."
            )

        return Path(
            root_text
        ).resolve()

    def _repository_paths(
        self,
    ) -> tuple[str, ...]:
        output = self._run_git(
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        )

        paths = tuple(
            sorted(
                {
                    item
                    for item
                    in output.split(
                        "\0"
                    )
                    if item
                }
            )
        )

        if not paths:
            raise ProjectInspectionError(
                "Repository contains no inspectable files."
            )

        return paths

    def _git_findings(
        self,
    ) -> tuple[str, ...]:
        head = self._run_git(
            "rev-parse",
            "HEAD",
        ).strip()

        branch = self._run_git(
            "branch",
            "--show-current",
        ).strip()

        status_output = self._run_git(
            "status",
            "--porcelain=v1",
        )

        status_lines = tuple(
            line
            for line
            in status_output.splitlines()
            if line.strip()
        )

        findings: list[str] = [
            f"git.head={head}",
            (
                "git.branch="
                f"{branch or 'DETACHED'}"
            ),
            (
                "git.clean="
                f"{not status_lines}"
            ),
            (
                "git.changed_paths="
                f"{len(status_lines)}"
            ),
        ]

        for line in status_lines:
            findings.append(
                f"git.change={line}"
            )

        return tuple(
            findings
        )

    @staticmethod
    def _is_test_path(
        path: str,
    ) -> bool:
        candidate = Path(
            path
        )

        parts = {
            part.lower()
            for part
            in candidate.parts
        }

        name = candidate.name.lower()

        return (
            "tests" in parts
            or "test" in parts
            or name.startswith(
                "test_"
            )
            or ".test." in name
            or ".spec." in name
        )

    @staticmethod
    def _is_manifest_path(
        path: str,
    ) -> bool:
        candidate = Path(
            path
        )

        if candidate.name in MANIFEST_NAMES:
            return True

        if candidate.name.endswith(
            ".lock"
        ):
            return True

        return False

    def _source_findings(
        self,
        paths: tuple[str, ...],
    ) -> tuple[str, ...]:
        findings: list[str] = []

        source_counts = {
            "python": 0,
            "typescript": 0,
            "rust": 0,
        }

        test_count = 0
        manifests: list[str] = []

        for relative_path in paths:
            absolute_path = (
                self.repository_root
                / relative_path
            )

            if self._is_test_path(
                relative_path
            ):
                test_count += 1

            if self._is_manifest_path(
                relative_path
            ):
                manifests.append(
                    relative_path
                )

            language = SOURCE_SUFFIXES.get(
                absolute_path.suffix.lower()
            )

            if language is None:
                continue

            if not absolute_path.is_file():
                continue

            source_counts[
                language
            ] += 1

            try:
                file_hash = _sha256_file(
                    absolute_path
                )

            except OSError:
                continue

            findings.append(
                (
                    "file.sha256="
                    f"{relative_path}::"
                    f"{file_hash}"
                )
            )

            text = _read_source_text(
                absolute_path
            )

            if text is None:
                continue

            if language == "python":
                symbols = _python_symbols(
                    text
                )

            elif language == "typescript":
                symbols = _typescript_symbols(
                    text
                )

            else:
                symbols = _rust_symbols(
                    text
                )

            for symbol in symbols:
                findings.append(
                    (
                        f"symbol.{language}="
                        f"{relative_path}::"
                        f"{symbol}"
                    )
                )

        findings.extend(
            [
                (
                    "repository.tracked_and_untracked_files="
                    f"{len(paths)}"
                ),
                (
                    "repository.python_files="
                    f"{source_counts['python']}"
                ),
                (
                    "repository.typescript_files="
                    f"{source_counts['typescript']}"
                ),
                (
                    "repository.rust_files="
                    f"{source_counts['rust']}"
                ),
                (
                    "repository.test_files="
                    f"{test_count}"
                ),
                (
                    "repository.manifests="
                    + ",".join(
                        sorted(
                            manifests
                        )
                    )
                ),
            ]
        )

        return tuple(
            findings
        )

    def inspect(
        self,
        *,
        requirement_id: str,
    ) -> RepositoryInspection:
        requirement_id = _require_text(
            requirement_id,
            field_name="requirement_id",
        )

        paths = self._repository_paths()

        findings = (
            self._git_findings()
            + self._source_findings(
                paths
            )
        )

        return RepositoryInspection.create(
            requirement_id=requirement_id,
            repository_root=str(
                self.repository_root
            ),
            inspected_paths=paths,
            findings=findings,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the live software repository "
            "without modifying it."
        )
    )

    parser.add_argument(
        "--repository-root",
        default=".",
    )

    parser.add_argument(
        "--requirement-id",
        required=True,
    )

    arguments = parser.parse_args()

    inspector = ProjectInspector(
        arguments.repository_root
    )

    inspection = inspector.inspect(
        requirement_id=(
            arguments.requirement_id
        )
    )

    print(
        json.dumps(
            inspection.to_dict(),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
