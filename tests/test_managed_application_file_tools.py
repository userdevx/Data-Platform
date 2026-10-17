from pathlib import Path

import pytest

import engine.tools.file_tools as file_tools
from engine.tools.file_tools import (
    FileToolError,
    ListManagedFilesTool,
    ReadManagedFilesTool,
    WriteManagedFilesTool,
    register_managed_workspace,
)


def _workspace(
    tmp_path: Path,
    monkeypatch,
):
    root = (
        tmp_path
        / "application-generation"
    )

    workspace = (
        root
        / "application-test"
    )

    workspace.mkdir(
        parents=True
    )

    monkeypatch.setattr(
        file_tools,
        "MANAGED_APPLICATION_ROOT",
        root,
    )

    workspace_id = (
        register_managed_workspace(
            workspace
        )
    )

    return (
        workspace,
        workspace_id,
    )


def test_new_file_can_be_created_without_prior_read(
    tmp_path,
    monkeypatch,
) -> None:
    workspace, workspace_id = (
        _workspace(
            tmp_path,
            monkeypatch,
        )
    )

    result = (
        WriteManagedFilesTool()
        .execute(
            {
                "workspace_id": (
                    workspace_id
                ),
                "files": [
                    {
                        "path": "main.py",
                        "content": (
                            'print("ok")\n'
                        ),
                    }
                ],
            },
            {},
        )
    )

    assert result["success"] is True

    assert (
        workspace
        / "main.py"
    ).read_text(
        encoding="utf-8"
    ) == 'print("ok")\n'


def test_existing_file_requires_complete_read_before_write(
    tmp_path,
    monkeypatch,
) -> None:
    workspace, workspace_id = (
        _workspace(
            tmp_path,
            monkeypatch,
        )
    )

    target = (
        workspace
        / "main.py"
    )

    target.write_text(
        "before\n",
        encoding="utf-8",
    )

    with pytest.raises(
        FileToolError,
        match=(
            "read completely"
        ),
    ):
        (
            WriteManagedFilesTool()
            .execute(
                {
                    "workspace_id": (
                        workspace_id
                    ),
                    "files": [
                        {
                            "path": (
                                "main.py"
                            ),
                            "content": (
                                "after\n"
                            ),
                        }
                    ],
                },
                {},
            )
        )

    (
        ReadManagedFilesTool()
        .execute(
            {
                "workspace_id": (
                    workspace_id
                ),
                "paths": [
                    "main.py"
                ],
            },
            {},
        )
    )

    result = (
        WriteManagedFilesTool()
        .execute(
            {
                "workspace_id": (
                    workspace_id
                ),
                "files": [
                    {
                        "path": "main.py",
                        "content": (
                            "after\n"
                        ),
                    }
                ],
            },
            {},
        )
    )

    assert result["success"] is True


def test_list_files_returns_paths_without_source_excerpts(
    tmp_path,
    monkeypatch,
) -> None:
    workspace, workspace_id = (
        _workspace(
            tmp_path,
            monkeypatch,
        )
    )

    (
        workspace
        / "source.py"
    ).write_text(
        "secret_source_text\n",
        encoding="utf-8",
    )

    result = (
        ListManagedFilesTool()
        .execute(
            {
                "workspace_id": (
                    workspace_id
                ),
                "path": ".",
                "recursive": True,
            },
            {},
        )
    )

    assert result["count"] == 1

    assert result["entries"] == [
        {
            "path": "source.py",
            "type": "file",
        }
    ]


def test_path_escape_is_blocked(
    tmp_path,
    monkeypatch,
) -> None:
    _, workspace_id = (
        _workspace(
            tmp_path,
            monkeypatch,
        )
    )

    with pytest.raises(
        FileToolError,
    ):
        (
            ReadManagedFilesTool()
            .execute(
                {
                    "workspace_id": (
                        workspace_id
                    ),
                    "paths": [
                        "../outside.txt"
                    ],
                },
                {},
            )
        )
