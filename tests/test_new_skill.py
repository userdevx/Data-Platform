"""Regression tests for scripts/new_skill.py against the real create-skill contract."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys


def _repo_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts" / "new_skill.py").is_file():
            return parent
    raise RuntimeError("scripts/new_skill.py not found above tests")


ROOT = _repo_root()
SCRIPT = ROOT / "scripts" / "new_skill.py"
CONTRACT = ROOT / "skills" / "create-skill" / "SKILL.md"


def _skills(tmp_path):
    skills = tmp_path / "skills"
    (skills / "create-skill").mkdir(parents=True)
    shutil.copy2(CONTRACT, skills / "create-skill" / "SKILL.md")
    return skills


def _run(skills, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--skills-dir", str(skills)],
        capture_output=True, text=True, encoding="utf-8",
    )


def _front_matter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    return {
        key.strip(): json.loads(value.strip())
        for key, _, value in (line.partition(":") for line in lines[1:end])
    }


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_creates_package_with_metadata_and_sections(tmp_path):
    skills = _skills(tmp_path)
    result = _run(skills, "demo-skill", "--name", "Demo",
                  "--description", "A demo.", "--tool", "email_read",
                  "--tool", "email_read")
    assert result.returncode == 0, result.stderr
    target = skills / "demo-skill" / "SKILL.md"
    meta = _front_matter(target)
    assert meta == {
        "schema_version": 1, "id": "demo-skill", "name": "Demo",
        "description": "A demo.", "version": "0.1.0",
        "required_tools": ["email_read"],
    }
    headings = [line for line in target.read_text(encoding="utf-8").splitlines()
                if line.startswith("## ")]
    assert len(headings) == 14


def test_refuses_existing_id(tmp_path):
    skills = _skills(tmp_path)
    assert _run(skills, "demo-skill", "--name", "D", "--description", "x").returncode == 0
    result = _run(skills, "demo-skill", "--name", "D", "--description", "x")
    assert result.returncode == 1
    assert "already exists" in result.stderr


def test_refuses_id_held_by_renamed_folder(tmp_path):
    skills = _skills(tmp_path)
    assert _run(skills, "demo-skill", "--name", "D", "--description", "x").returncode == 0
    (skills / "demo-skill").rename(skills / "renamed")
    result = _run(skills, "demo-skill", "--name", "D", "--description", "x")
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert not (skills / "demo-skill").exists()


def test_rejects_multiline_values_and_leaves_nothing(tmp_path):
    skills = _skills(tmp_path)
    for value in ("a\nb", "a\rb", "a\u2028b", "a\u0085b"):
        result = _run(skills, "line-skill", "--name", "D", "--description", value)
        assert result.returncode == 1, repr(value)
        assert "single line" in result.stderr, (repr(value), result.stderr)
        assert not (skills / "line-skill").exists(), repr(value)


def test_rejects_empty_name(tmp_path):
    skills = _skills(tmp_path)
    result = _run(skills, "empty-skill", "--name", "   ", "--description", "x")
    assert result.returncode == 1
    assert "must not be empty" in result.stderr
    assert not (skills / "empty-skill").exists()


def test_invalid_metadata_error_names_file_and_key(tmp_path):
    skills = _skills(tmp_path)
    (skills / "broken").mkdir()
    (skills / "broken" / "SKILL.md").write_text("---\nid: oops\n---\n", encoding="utf-8")
    result = _run(skills, "new-skill", "--name", "D", "--description", "x")
    assert result.returncode == 1
    assert str(skills / "broken" / "SKILL.md") in result.stderr
    assert "'id'" in result.stderr
    assert not (skills / "new-skill").exists()


def test_contract_is_unchanged(tmp_path):
    skills = _skills(tmp_path)
    contract = skills / "create-skill" / "SKILL.md"
    before = _digest(contract)
    assert _run(skills, "demo-skill", "--name", "D", "--description", "x").returncode == 0
    assert _digest(contract) == before
    assert _digest(CONTRACT) == before
