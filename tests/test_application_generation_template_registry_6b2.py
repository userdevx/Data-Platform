from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.application_generation.template_registry import (
    APPLICATION_TYPES,
    ApplicationTemplateRegistry,
    TemplateRegistryError,
)


def create_template(
    root: Path,
    application_type: str,
    files: dict[str, str],
) -> Path:
    folder = root / APPLICATION_TYPES[application_type]
    folder.mkdir(parents=True)

    for name, content in files.items():
        source = folder / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(content, encoding="utf-8")

    return folder


def write_manifest(folder: Path, files: dict[str, str]) -> None:
    (folder / "manifest.json").write_text(
        json.dumps({"version": 1, "files": files}),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "application_type",
    list(APPLICATION_TYPES),
)
def test_loads_real_template_files(
    tmp_path: Path,
    application_type: str,
) -> None:
    folder = create_template(
        tmp_path,
        application_type,
        {"main.template": "ORIGINAL_TEMPLATE_CONTENT\n"},
    )
    write_manifest(folder, {"main.py": "main.template"})

    registry = ApplicationTemplateRegistry(tmp_path)
    result = registry.load(application_type)

    assert result == {
        "main.py": "ORIGINAL_TEMPLATE_CONTENT\n"
    }


def test_rejects_unsupported_type(tmp_path: Path) -> None:
    registry = ApplicationTemplateRegistry(tmp_path)

    with pytest.raises(TemplateRegistryError):
        registry.load("Unknown application")


def test_rejects_template_path_traversal(tmp_path: Path) -> None:
    folder = create_template(
        tmp_path,
        "Web application",
        {"main.template": "safe"},
    )
    write_manifest(folder, {"index.html": "../outside"})

    with pytest.raises(TemplateRegistryError):
        ApplicationTemplateRegistry(tmp_path).load(
            "Web application"
        )


def test_rejects_output_path_traversal(tmp_path: Path) -> None:
    folder = create_template(
        tmp_path,
        "Web application",
        {"main.template": "safe"},
    )
    write_manifest(folder, {"../outside": "main.template"})

    with pytest.raises(TemplateRegistryError):
        ApplicationTemplateRegistry(tmp_path).load(
            "Web application"
        )


def test_rejects_symlinked_template(tmp_path: Path) -> None:
    folder = tmp_path / "web"
    folder.mkdir()

    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET", encoding="utf-8")

    (folder / "linked.template").symlink_to(outside)
    write_manifest(
        folder,
        {"index.html": "linked.template"},
    )

    with pytest.raises(TemplateRegistryError):
        ApplicationTemplateRegistry(tmp_path).load(
            "Web application"
        )


def test_missing_manifest_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()

    with pytest.raises(TemplateRegistryError):
        ApplicationTemplateRegistry(tmp_path).load(
            "Web application"
        )


def test_rejects_unsupported_manifest_version(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "web"
    folder.mkdir()

    (folder / "manifest.json").write_text(
        json.dumps({"version": 2, "files": {}}),
        encoding="utf-8",
    )

    with pytest.raises(TemplateRegistryError):
        ApplicationTemplateRegistry(tmp_path).load(
            "Web application"
        )


def test_rejects_symlinked_registry_root(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    external.mkdir()

    registry_root = tmp_path / "templates"
    registry_root.symlink_to(
        external,
        target_is_directory=True,
    )

    with pytest.raises(TemplateRegistryError):
        ApplicationTemplateRegistry(registry_root).load(
            "Web application"
        )
