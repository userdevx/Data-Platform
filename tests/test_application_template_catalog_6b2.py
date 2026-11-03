from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.application_generation.template_catalog import (
    ApplicationTemplateCatalog,
    TemplateCatalogError,
)


def make_template(
    root: Path,
    directory: str,
    template_id: str,
    *,
    destination: str = "src/main.py",
    source: str = "main.py.tpl",
    mode: str = "python-string",
) -> Path:
    folder = root / directory
    folder.mkdir(parents=True)

    (folder / "main.py.tpl").write_text(
        'print("DataWorc")\n',
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "template_id": template_id,
        "display_name": "Test Application",
        "category": "desktop",
        "language": "python",
        "framework": "tkinter",
        "platforms": ["linux"],
        "capabilities": ["gui", "local-execution"],
        "files": [
            {
                "source": source,
                "destination": destination,
                "render_mode": mode,
            }
        ],
    }

    (folder / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    return folder


def test_discovers_registered_template(tmp_path: Path):
    make_template(
        tmp_path,
        "example",
        "python-desktop-basic",
    )

    catalog = ApplicationTemplateCatalog(tmp_path)

    result = catalog.discover()

    assert "python-desktop-basic" in result
    assert result["python-desktop-basic"].language == "python"
    assert result["python-desktop-basic"].framework == "tkinter"


def test_new_category_requires_no_registry_changes(tmp_path: Path):
    folder = make_template(
        tmp_path,
        "service",
        "python-service-basic",
    )

    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    manifest["category"] = "service"
    manifest["framework"] = "fastapi"

    manifest_path.write_text(json.dumps(manifest))

    result = ApplicationTemplateCatalog(tmp_path).get(
        "python-service-basic"
    )

    assert result.category == "service"
    assert result.framework == "fastapi"


def test_reads_real_source_file(tmp_path: Path):
    make_template(
        tmp_path,
        "example",
        "python-desktop-basic",
    )

    result = ApplicationTemplateCatalog(tmp_path).read_files(
        "python-desktop-basic"
    )

    assert result == {
        "src/main.py": 'print("DataWorc")\n'
    }


def test_rejects_unsafe_output_path(tmp_path: Path):
    make_template(
        tmp_path,
        "example",
        "python-desktop-basic",
        destination="../outside.py",
    )

    with pytest.raises(TemplateCatalogError):
        ApplicationTemplateCatalog(tmp_path).discover()


def test_rejects_unsafe_source_path(tmp_path: Path):
    make_template(
        tmp_path,
        "example",
        "python-desktop-basic",
        source="../../outside.txt",
    )

    with pytest.raises(TemplateCatalogError):
        ApplicationTemplateCatalog(tmp_path).discover()


def test_rejects_unregistered_render_mode(tmp_path: Path):
    make_template(
        tmp_path,
        "example",
        "python-desktop-basic",
        mode="execute-python",
    )

    with pytest.raises(TemplateCatalogError):
        ApplicationTemplateCatalog(tmp_path).discover()


def test_rejects_duplicate_ids(tmp_path: Path):
    make_template(
        tmp_path,
        "first",
        "duplicate-template",
    )
    make_template(
        tmp_path,
        "second",
        "duplicate-template",
    )

    with pytest.raises(TemplateCatalogError):
        ApplicationTemplateCatalog(tmp_path).discover()


def test_rejects_symlinked_source(tmp_path: Path):
    folder = make_template(
        tmp_path,
        "example",
        "python-desktop-basic",
        source="linked.tpl",
    )

    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    (folder / "linked.tpl").symlink_to(outside)

    with pytest.raises(TemplateCatalogError):
        ApplicationTemplateCatalog(tmp_path).discover()


def test_rejects_symlinked_template_directory(tmp_path: Path):
    actual = tmp_path / "_external"
    make_template(
        actual,
        "example",
        "python-desktop-basic",
    )

    (tmp_path / "linked").symlink_to(
        actual / "example",
        target_is_directory=True,
    )

    with pytest.raises(TemplateCatalogError):
        ApplicationTemplateCatalog(tmp_path).discover()


def test_missing_template_fails_closed(tmp_path: Path):
    catalog = ApplicationTemplateCatalog(tmp_path)

    with pytest.raises(TemplateCatalogError):
        catalog.get("not-registered")


def test_skips_rust_snapshot_directory(tmp_path: Path):
    (tmp_path / "_rust_snapshot").mkdir()

    catalog = ApplicationTemplateCatalog(tmp_path)

    assert catalog.discover() == {}
