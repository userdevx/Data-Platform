from __future__ import annotations

from pathlib import Path

import pytest

from engine.application_generation.workspace import (
    ApplicationWorkspaceError,
    ApplicationWorkspaceManager,
)


def test_creates_real_managed_workspace(
    tmp_path: Path,
) -> None:
    manager = ApplicationWorkspaceManager(tmp_path)

    workspace = manager.create("inventory-app")

    expected = (
        tmp_path
        / "var"
        / "application-generation"
        / "inventory-app"
    )

    assert workspace.application_id == "inventory-app"
    assert workspace.path == expected
    assert expected.is_dir()

    reopened = manager.get_existing("inventory-app")

    assert reopened.path == expected


@pytest.mark.parametrize(
    "identifier",
    [
        "../outside",
        "/tmp/outside",
        "nested/application",
        ".",
        "..",
        "",
        "Invalid Name",
        "-application",
        "application\\other",
        "a" * 65,
    ],
)
def test_rejects_unsafe_identifiers(
    tmp_path: Path,
    identifier: str,
) -> None:
    manager = ApplicationWorkspaceManager(tmp_path)

    with pytest.raises(ApplicationWorkspaceError):
        manager.create(identifier)


def test_existing_workspace_cannot_be_overwritten(
    tmp_path: Path,
) -> None:
    manager = ApplicationWorkspaceManager(tmp_path)

    workspace = manager.create("existing-app")

    existing_file = workspace.path / "existing.txt"
    existing_file.write_text(
        "PRESERVE_THIS",
        encoding="utf-8",
    )

    with pytest.raises(ApplicationWorkspaceError):
        manager.create("existing-app")

    assert existing_file.read_text(
        encoding="utf-8"
    ) == "PRESERVE_THIS"


def test_rejects_symlinked_workspace_root(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    external.mkdir()

    (tmp_path / "var").symlink_to(
        external,
        target_is_directory=True,
    )

    manager = ApplicationWorkspaceManager(tmp_path)

    with pytest.raises(ApplicationWorkspaceError):
        manager.create("escape-app")

    assert not (
        external / "application-generation" / "escape-app"
    ).exists()


def test_rejects_symlinked_existing_workspace(
    tmp_path: Path,
) -> None:
    manager = ApplicationWorkspaceManager(tmp_path)
    manager.workspace_root.mkdir(parents=True)

    external = tmp_path / "external"
    external.mkdir()

    (manager.workspace_root / "linked-app").symlink_to(
        external,
        target_is_directory=True,
    )

    with pytest.raises(ApplicationWorkspaceError):
        manager.get_existing("linked-app")


def test_application_workspace_is_under_managed_root(
    tmp_path: Path,
) -> None:
    manager = ApplicationWorkspaceManager(tmp_path)

    first = manager.create("project-one")
    second = manager.create("project-two")

    assert first.path != second.path

    assert first.path.is_relative_to(
        manager.workspace_root
    )
    assert second.path.is_relative_to(
        manager.workspace_root
    )
