from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import (
    asdict,
    dataclass,
)
from pathlib import Path, PurePosixPath
from typing import Literal


EntryType = Literal[
    "file",
    "directory",
    "symlink",
    "other",
]


class FilesystemEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FilesystemEntry:
    path: str
    entry_type: EntryType
    mode: int
    size: int
    sha256: str | None = None
    symlink_target: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FilesystemSnapshot:
    entries: tuple[FilesystemEntry, ...]

    def to_dict(self) -> dict:
        return {
            "entries": [
                entry.to_dict()
                for entry in self.entries
            ]
        }


@dataclass(frozen=True, slots=True)
class FilesystemChange:
    path: str
    change_type: str
    before: FilesystemEntry | None
    after: FilesystemEntry | None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "before": (
                self.before.to_dict()
                if self.before is not None
                else None
            ),
            "after": (
                self.after.to_dict()
                if self.after is not None
                else None
            ),
        }


def _file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb",
        buffering=0,
    ) as stream:
        while True:
            chunk = stream.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _entry_type(
    mode: int,
) -> EntryType:
    if stat.S_ISREG(mode):
        return "file"

    if stat.S_ISDIR(mode):
        return "directory"

    if stat.S_ISLNK(mode):
        return "symlink"

    return "other"


def snapshot_filesystem(
    root: Path,
) -> FilesystemSnapshot:
    root = Path(root)

    if (
        not root.is_dir()
        or root.is_symlink()
    ):
        raise FilesystemEvidenceError(
            f"snapshot root is not a real directory: {root}"
        )

    entries: list[
        FilesystemEntry
    ] = []

    for directory, dirnames, filenames in os.walk(
        root,
        followlinks=False,
    ):
        dirnames.sort()
        filenames.sort()

        for name in sorted(
            dirnames + filenames
        ):
            path = (
                Path(directory)
                / name
            )

            try:
                info = os.lstat(
                    path
                )
            except OSError as exc:
                raise FilesystemEvidenceError(
                    f"unable to stat workspace entry: {path}"
                ) from exc

            relative = PurePosixPath(
                path.relative_to(
                    root
                ).as_posix()
            )

            entry_type = _entry_type(
                info.st_mode
            )

            sha256: str | None = None
            symlink_target: str | None = None

            if entry_type == "file":
                try:
                    sha256 = _file_sha256(
                        path
                    )
                except OSError as exc:
                    raise FilesystemEvidenceError(
                        f"unable to hash workspace file: {path}"
                    ) from exc

            elif entry_type == "symlink":
                try:
                    symlink_target = os.readlink(
                        path
                    )
                except OSError as exc:
                    raise FilesystemEvidenceError(
                        f"unable to read symlink: {path}"
                    ) from exc

            entries.append(
                FilesystemEntry(
                    path=str(relative),
                    entry_type=entry_type,
                    mode=stat.S_IMODE(
                        info.st_mode
                    ),
                    size=info.st_size,
                    sha256=sha256,
                    symlink_target=symlink_target,
                )
            )

    entries.sort(
        key=lambda item: item.path
    )

    return FilesystemSnapshot(
        entries=tuple(entries)
    )


def diff_filesystems(
    before: FilesystemSnapshot,
    after: FilesystemSnapshot,
) -> tuple[FilesystemChange, ...]:
    before_map = {
        entry.path: entry
        for entry in before.entries
    }

    after_map = {
        entry.path: entry
        for entry in after.entries
    }

    changes: list[
        FilesystemChange
    ] = []

    for path in sorted(
        set(before_map)
        | set(after_map)
    ):
        old = before_map.get(
            path
        )

        new = after_map.get(
            path
        )

        if old is None:
            changes.append(
                FilesystemChange(
                    path=path,
                    change_type="added",
                    before=None,
                    after=new,
                )
            )
            continue

        if new is None:
            changes.append(
                FilesystemChange(
                    path=path,
                    change_type="removed",
                    before=old,
                    after=None,
                )
            )
            continue

        if old.entry_type != new.entry_type:
            change_type = "type_changed"

        elif (
            old.entry_type == "file"
            and old.sha256 != new.sha256
        ):
            change_type = "modified"

        elif (
            old.entry_type == "symlink"
            and old.symlink_target
            != new.symlink_target
        ):
            change_type = (
                "symlink_target_changed"
            )

        elif (
            old.mode != new.mode
            or old.size != new.size
        ):
            change_type = (
                "metadata_changed"
            )

        else:
            continue

        changes.append(
            FilesystemChange(
                path=path,
                change_type=change_type,
                before=old,
                after=new,
            )
        )

    return tuple(changes)
