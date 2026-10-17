from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.security.intelligence_execution_manifest import (
    INTELLIGENCE_EXECUTION_MANIFEST,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

MANAGED_APPLICATION_ROOT = (
    PROJECT_ROOT
    / "var"
    / "application-generation"
).resolve()


class FileToolError(Exception):
    pass


@dataclass
class ManagedWorkspaceState:
    workspace_id: str
    root: Path
    read_hashes: dict[
        str,
        str,
    ] = field(
        default_factory=dict
    )


_MANAGED_WORKSPACES: dict[
    str,
    ManagedWorkspaceState,
] = {}


def _sha256_text(
    content: str,
) -> str:
    return hashlib.sha256(
        content.encode(
            "utf-8"
        )
    ).hexdigest()


def _is_within(
    child: Path,
    parent: Path,
) -> bool:
    return (
        child == parent
        or parent in child.parents
    )


def register_managed_workspace(
    root: str | Path,
) -> str:
    workspace_root = (
        Path(root)
        .expanduser()
        .resolve()
    )

    managed_root = (
        MANAGED_APPLICATION_ROOT
        .expanduser()
        .resolve()
    )

    if not _is_within(
        workspace_root,
        managed_root,
    ):
        raise FileToolError(
            "Workspace is outside the "
            "managed application root."
        )

    if not workspace_root.is_dir():
        raise FileToolError(
            "Managed workspace does not exist."
        )

    workspace_id = (
        "workspace-"
        + uuid4().hex
    )

    _MANAGED_WORKSPACES[
        workspace_id
    ] = ManagedWorkspaceState(
        workspace_id=workspace_id,
        root=workspace_root,
    )

    return workspace_id


def release_managed_workspace(
    workspace_id: str,
) -> None:
    _MANAGED_WORKSPACES.pop(
        workspace_id,
        None,
    )


def _workspace(
    workspace_id: str,
) -> ManagedWorkspaceState:
    state = (
        _MANAGED_WORKSPACES.get(
            str(workspace_id)
        )
    )

    if state is None:
        raise FileToolError(
            "Unknown managed workspace."
        )

    return state


def _resolve_managed_path(
    state: ManagedWorkspaceState,
    relative_path: str,
    *,
    allow_root: bool = False,
) -> Path:
    if not isinstance(
        relative_path,
        str,
    ):
        raise FileToolError(
            "Path must be text."
        )

    candidate = Path(
        relative_path
    )

    if candidate.is_absolute():
        raise FileToolError(
            "Absolute paths are blocked."
        )

    if ".." in candidate.parts:
        raise FileToolError(
            "Path traversal is blocked."
        )

    if (
        relative_path.strip()
        in {
            "",
            ".",
        }
    ):
        if allow_root:
            return state.root

        raise FileToolError(
            "A file path is required."
        )

    target = (
        state.root
        / candidate
    ).resolve()

    if not _is_within(
        target,
        state.root,
    ):
        raise FileToolError(
            "Path escapes managed workspace."
        )

    relative_parts = (
        target
        .relative_to(
            state.root
        )
        .parts
    )

    if ".git" in relative_parts:
        raise FileToolError(
            "Direct Git-internal access "
            "is blocked."
        )

    if target.name == ".env" or (
        target.name.startswith(
            ".env."
        )
    ):
        raise FileToolError(
            "Credential environment files "
            "cannot be modified by "
            "Application Generation."
        )

    return target


def read_approved_file(
    path: str,
) -> dict:
    file_path = Path(
        path
    )

    if file_path.is_absolute():
        raise FileToolError(
            "Absolute paths are blocked."
        )

    if ".." in file_path.parts:
        raise FileToolError(
            "Path traversal is blocked."
        )

    if not file_path.exists():
        raise FileToolError(
            f"File does not exist: {path}"
        )

    if not file_path.is_file():
        raise FileToolError(
            f"Path is not a file: {path}"
        )

    rule = (
        INTELLIGENCE_EXECUTION_MANIFEST[
            "files.read_approved"
        ]
    )

    max_file_size_mb = (
        rule.get(
            "max_file_size_mb",
            25,
        )
    )

    max_file_size_bytes = (
        max_file_size_mb
        * 1024
        * 1024
    )

    file_size = (
        file_path.stat().st_size
    )

    if (
        file_size
        > max_file_size_bytes
    ):
        raise FileToolError(
            f"File exceeds max size: {path}"
        )

    content = (
        file_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    return {
        "source": "filesystem",
        "category": "approved_file",
        "data_type": "file_text",
        "value": content,
        "unit": "text",
        "path": str(
            file_path
        ),
        "size_bytes": file_size,
    }


class ListManagedFilesTool:
    name = "list_files"

    def execute(
        self,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del context

        state = _workspace(
            str(
                arguments.get(
                    "workspace_id",
                    "",
                )
            )
        )

        relative = str(
            arguments.get(
                "path",
                ".",
            )
        )

        recursive = arguments.get(
            "recursive",
            False,
        )

        if not isinstance(
            recursive,
            bool,
        ):
            raise FileToolError(
                "recursive must be boolean."
            )

        base = _resolve_managed_path(
            state,
            relative,
            allow_root=True,
        )

        if not base.is_dir():
            raise FileToolError(
                "List target is not a directory."
            )

        iterator = (
            base.rglob("*")
            if recursive
            else base.iterdir()
        )

        entries: list[
            dict[str, str]
        ] = []

        for item in iterator:
            try:
                relative_item = (
                    item.relative_to(
                        state.root
                    )
                )
            except ValueError:
                continue

            if ".git" in (
                relative_item.parts
            ):
                continue

            entries.append(
                {
                    "path": str(
                        relative_item
                    ),
                    "type": (
                        "directory"
                        if item.is_dir()
                        else "file"
                    ),
                }
            )

            if len(entries) >= 250:
                break

        entries.sort(
            key=lambda item: (
                item["path"]
            )
        )

        return {
            "success": True,
            "workspace_id": (
                state.workspace_id
            ),
            "path": relative,
            "count": len(
                entries
            ),
            "entries": entries,
        }


class ReadManagedFilesTool:
    name = "read_files"

    MAX_FILES = 16
    MAX_FILE_BYTES = (
        100 * 1024
    )
    MAX_BATCH_BYTES = (
        400 * 1024
    )

    def execute(
        self,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del context

        state = _workspace(
            str(
                arguments.get(
                    "workspace_id",
                    "",
                )
            )
        )

        paths = arguments.get(
            "paths"
        )

        if (
            not isinstance(
                paths,
                list,
            )
            or not paths
        ):
            raise FileToolError(
                "paths must be a non-empty list."
            )

        if (
            len(paths)
            > self.MAX_FILES
        ):
            raise FileToolError(
                "Too many files requested."
            )

        results: list[
            dict[str, Any]
        ] = []

        total_bytes = 0

        for relative in paths:
            if not isinstance(
                relative,
                str,
            ):
                raise FileToolError(
                    "Every path must be text."
                )

            target = (
                _resolve_managed_path(
                    state,
                    relative,
                )
            )

            if not target.is_file():
                raise FileToolError(
                    "File does not exist: "
                    + relative
                )

            size = (
                target.stat().st_size
            )

            if (
                size
                > self.MAX_FILE_BYTES
            ):
                raise FileToolError(
                    "File exceeds managed "
                    "read limit: "
                    + relative
                )

            content = (
                target.read_text(
                    encoding="utf-8"
                )
            )

            encoded_size = len(
                content.encode(
                    "utf-8"
                )
            )

            total_bytes += (
                encoded_size
            )

            if (
                total_bytes
                > self.MAX_BATCH_BYTES
            ):
                raise FileToolError(
                    "Managed read batch "
                    "exceeds size limit."
                )

            digest = (
                _sha256_text(
                    content
                )
            )

            normalized_relative = str(
                target.relative_to(
                    state.root
                )
            )

            state.read_hashes[
                normalized_relative
            ] = digest

            results.append(
                {
                    "path": (
                        normalized_relative
                    ),
                    "content": content,
                    "bytes": (
                        encoded_size
                    ),
                    "sha256": digest,
                }
            )

        return {
            "success": True,
            "workspace_id": (
                state.workspace_id
            ),
            "file_count": len(
                results
            ),
            "files": results,
        }


class WriteManagedFilesTool:
    name = "write_files"

    MAX_FILES = 32
    MAX_FILE_BYTES = (
        250 * 1024
    )

    def execute(
        self,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del context

        state = _workspace(
            str(
                arguments.get(
                    "workspace_id",
                    "",
                )
            )
        )

        files = arguments.get(
            "files"
        )

        if (
            not isinstance(
                files,
                list,
            )
            or not files
        ):
            raise FileToolError(
                "files must be a non-empty list."
            )

        if (
            len(files)
            > self.MAX_FILES
        ):
            raise FileToolError(
                "Too many files in one write."
            )

        prepared: list[
            tuple[
                str,
                Path,
                str,
                str | None,
            ]
        ] = []

        for item in files:
            if not isinstance(
                item,
                dict,
            ):
                raise FileToolError(
                    "Every file write must "
                    "be an object."
                )

            relative = item.get(
                "path"
            )

            content = item.get(
                "content"
            )

            if not isinstance(
                relative,
                str,
            ):
                raise FileToolError(
                    "File path must be text."
                )

            if not isinstance(
                content,
                str,
            ):
                raise FileToolError(
                    "File content must be text."
                )

            content_size = len(
                content.encode(
                    "utf-8"
                )
            )

            if (
                content_size
                > self.MAX_FILE_BYTES
            ):
                raise FileToolError(
                    "Generated file exceeds "
                    "write limit: "
                    + relative
                )

            target = (
                _resolve_managed_path(
                    state,
                    relative,
                )
            )

            normalized_relative = str(
                target.relative_to(
                    state.root
                )
            )

            before_sha256: str | None = (
                None
            )

            if target.exists():
                if not target.is_file():
                    raise FileToolError(
                        "Write target exists "
                        "but is not a file: "
                        + relative
                    )

                before_content = (
                    target.read_text(
                        encoding="utf-8"
                    )
                )

                before_sha256 = (
                    _sha256_text(
                        before_content
                    )
                )

                read_sha256 = (
                    state.read_hashes.get(
                        normalized_relative
                    )
                )

                if (
                    read_sha256
                    != before_sha256
                ):
                    raise FileToolError(
                        "Existing files must be "
                        "read completely before "
                        "replacement: "
                        + relative
                    )

            prepared.append(
                (
                    normalized_relative,
                    target,
                    content,
                    before_sha256,
                )
            )

        results: list[
            dict[str, Any]
        ] = []

        for (
            relative,
            target,
            content,
            before_sha256,
        ) in prepared:
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary = (
                target.with_name(
                    target.name
                    + ".application-generation-tmp"
                )
            )

            temporary.write_text(
                content,
                encoding="utf-8",
            )

            os.replace(
                temporary,
                target,
            )

            actual = (
                target.read_text(
                    encoding="utf-8"
                )
            )

            after_sha256 = (
                _sha256_text(
                    actual
                )
            )

            verified = (
                actual == content
            )

            if not verified:
                raise FileToolError(
                    "Written file failed "
                    "read-back verification: "
                    + relative
                )

            # A write invalidates the previous
            # read revision. The file must be
            # read again before another write.
            state.read_hashes.pop(
                relative,
                None,
            )

            results.append(
                {
                    "path": relative,
                    "before_sha256": (
                        before_sha256
                    ),
                    "after_sha256": (
                        after_sha256
                    ),
                    "changed": (
                        before_sha256
                        != after_sha256
                    ),
                    "bytes_written": len(
                        actual.encode(
                            "utf-8"
                        )
                    ),
                    "verified": True,
                }
            )

        return {
            "success": True,
            "workspace_id": (
                state.workspace_id
            ),
            "file_count": len(
                results
            ),
            "files": results,
        }
