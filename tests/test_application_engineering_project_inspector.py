from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from engine.application_engineering.project_inspector import (
    ProjectInspectionError,
    ProjectInspector,
)


def run_git(
    root: Path,
    *arguments: str,
) -> str:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(
                root
            ),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return completed.stdout


def create_repository(
    root: Path,
) -> dict[str, str]:
    if shutil.which(
        "git"
    ) is None:
        pytest.skip(
            "Git is required for this test."
        )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_git(
        root,
        "init",
    )

    run_git(
        root,
        "config",
        "user.email",
        "test@example.invalid",
    )

    run_git(
        root,
        "config",
        "user.name",
        "Test Runtime",
    )

    python_symbol = (
        "python_"
        + uuid4().hex[:10]
    )

    typescript_symbol = (
        "typescript_"
        + uuid4().hex[:10]
    )

    rust_symbol = (
        "rust_"
        + uuid4().hex[:10]
    )

    source_directory = (
        root
        / "source"
    )

    source_directory.mkdir()

    python_path = (
        source_directory
        / "module.py"
    )

    python_path.write_text(
        (
            f"def {python_symbol}():\n"
            "    return True\n"
        ),
        encoding="utf-8",
    )

    typescript_path = (
        source_directory
        / "component.ts"
    )

    typescript_path.write_text(
        (
            "export function "
            f"{typescript_symbol}() {{\n"
            "  return true;\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    rust_path = (
        source_directory
        / "module.rs"
    )

    rust_path.write_text(
        (
            f"pub fn {rust_symbol}() "
            "-> bool {\n"
            "    true\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    tests_directory = (
        root
        / "tests"
    )

    tests_directory.mkdir()

    (
        tests_directory
        / "test_runtime.py"
    ).write_text(
        "def test_runtime():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    (
        root
        / "pyproject.toml"
    ).write_text(
        "[project]\n"
        'name = "runtime-project"\n'
        'version = "0.0.0"\n',
        encoding="utf-8",
    )

    run_git(
        root,
        "add",
        "--",
        ".",
    )

    run_git(
        root,
        "commit",
        "-m",
        "Initial test repository",
    )

    return {
        "python_symbol": (
            python_symbol
        ),
        "typescript_symbol": (
            typescript_symbol
        ),
        "rust_symbol": (
            rust_symbol
        ),
    }


def test_live_inspector_reads_repository(
    tmp_path: Path,
) -> None:
    symbols = create_repository(
        tmp_path
    )

    requirement_id = (
        "requirement-"
        + uuid4().hex
    )

    inspection = ProjectInspector(
        tmp_path
    ).inspect(
        requirement_id=(
            requirement_id
        )
    )

    assert (
        inspection.requirement_id
        == requirement_id
    )

    assert (
        Path(
            inspection.repository_root
        )
        == tmp_path.resolve()
    )

    assert inspection.inspected_paths

    findings = "\n".join(
        inspection.findings
    )

    assert "git.head=" in findings

    assert (
        "repository.python_files="
        in findings
    )

    assert (
        "repository.typescript_files="
        in findings
    )

    assert (
        "repository.rust_files="
        in findings
    )

    assert (
        symbols[
            "python_symbol"
        ]
        in findings
    )

    assert (
        symbols[
            "typescript_symbol"
        ]
        in findings
    )

    assert (
        symbols[
            "rust_symbol"
        ]
        in findings
    )


def test_inspector_records_dirty_git_state(
    tmp_path: Path,
) -> None:
    create_repository(
        tmp_path
    )

    (
        tmp_path
        / "source"
        / "module.py"
    ).write_text(
        (
            "def changed_runtime_symbol():\n"
            "    return False\n"
        ),
        encoding="utf-8",
    )

    inspection = ProjectInspector(
        tmp_path
    ).inspect(
        requirement_id=(
            "requirement-"
            + uuid4().hex
        )
    )

    findings = "\n".join(
        inspection.findings
    )

    assert "git.clean=False" in findings
    assert "git.changed_paths=1" in findings


def test_inspection_is_read_only(
    tmp_path: Path,
) -> None:
    create_repository(
        tmp_path
    )

    before = run_git(
        tmp_path,
        "status",
        "--porcelain=v1",
    )

    ProjectInspector(
        tmp_path
    ).inspect(
        requirement_id=(
            "requirement-"
            + uuid4().hex
        )
    )

    after = run_git(
        tmp_path,
        "status",
        "--porcelain=v1",
    )

    assert before == after


def test_inspector_requires_git_repository(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ProjectInspectionError
    ):
        ProjectInspector(
            tmp_path
        )
