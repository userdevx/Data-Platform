from __future__ import annotations

import io
import os
import stat
import tarfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from engine.sandbox.models import SandboxRequest


class WorkspaceMode(str, Enum):
    NONE = "none"
    READ_ONLY = "read-only"
    READ_WRITE = "read-write"


def workspace_mode(request: SandboxRequest) -> WorkspaceMode:
    if request.working_directory is None:
        return WorkspaceMode.NONE

    if request.writable_workspace:
        return WorkspaceMode.READ_WRITE

    return WorkspaceMode.READ_ONLY


class WorkspaceViolation(ValueError):
    """A workspace or archive tried to cross the workspace boundary."""


@dataclass(frozen=True, slots=True)
class WorkspaceLimits:
    max_entries: int = 10_000
    max_total_bytes: int = 256 * 1024 * 1024
    max_file_bytes: int = 64 * 1024 * 1024


_FILE_MODE = 0o644
_EXEC_MODE = 0o755
_DIR_MODE = 0o755


def _safe_relative(name: str) -> PurePosixPath:
    if not name or "\x00" in name or "\\" in name:
        raise WorkspaceViolation(f"invalid member name: {name!r}")

    path = PurePosixPath(name)

    if path.is_absolute():
        raise WorkspaceViolation(f"absolute path: {name!r}")

    parts = [part for part in path.parts if part not in ("", ".")]

    if not parts:
        raise WorkspaceViolation(f"empty member name: {name!r}")

    if ".." in parts:
        raise WorkspaceViolation(f"parent traversal: {name!r}")

    return PurePosixPath(*parts)


def _symlink_stays_inside(
    member: PurePosixPath,
    target: str,
) -> bool:
    if not target or target.startswith("/") or "\x00" in target:
        return False

    depth = len(member.parent.parts)

    for part in PurePosixPath(target).parts:
        if part == "..":
            depth -= 1

            if depth < 0:
                return False
        elif part not in ("", "."):
            depth += 1

    return True


def _file_mode(mode: int) -> int:
    return _EXEC_MODE if mode & 0o111 else _FILE_MODE


def pack_workspace(
    source: Path,
    limits: WorkspaceLimits = WorkspaceLimits(),
) -> bytes:
    """Archive a workspace for transfer into a guest.

    Only regular files, directories and symlinks that stay inside the
    workspace are allowed. Ownership is normalised and setuid/setgid
    bits are dropped. Entries are sorted, so the archive is
    deterministic for identical content.
    """

    source = Path(source)

    if not source.is_dir() or source.is_symlink():
        raise WorkspaceViolation(f"not a real directory: {source}")

    buffer = io.BytesIO()
    entries = 0
    total = 0

    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for directory, dirnames, filenames in os.walk(
            source,
            followlinks=False,
        ):
            dirnames.sort()

            for name in sorted(dirnames + filenames):
                path = Path(directory) / name
                relative = PurePosixPath(
                    path.relative_to(source).as_posix()
                )
                info = os.lstat(path)

                entries += 1

                if entries > limits.max_entries:
                    raise WorkspaceViolation(
                        f"workspace has more than {limits.max_entries} entries"
                    )

                member = tarfile.TarInfo(relative.as_posix())
                member.uid = member.gid = 0
                member.uname = member.gname = "root"
                member.mtime = int(info.st_mtime)

                if stat.S_ISLNK(info.st_mode):
                    target = os.readlink(path)

                    if not _symlink_stays_inside(relative, target):
                        raise WorkspaceViolation(
                            f"symlink leaves workspace: {relative} -> {target}"
                        )

                    member.type = tarfile.SYMTYPE
                    member.linkname = target
                    member.mode = 0o777
                    archive.addfile(member)
                elif stat.S_ISDIR(info.st_mode):
                    member.type = tarfile.DIRTYPE
                    member.mode = _DIR_MODE
                    archive.addfile(member)
                elif stat.S_ISREG(info.st_mode):
                    if info.st_size > limits.max_file_bytes:
                        raise WorkspaceViolation(
                            f"file too large: {relative} ({info.st_size} bytes)"
                        )

                    total += info.st_size

                    if total > limits.max_total_bytes:
                        raise WorkspaceViolation(
                            "workspace exceeds "
                            f"{limits.max_total_bytes} bytes"
                        )

                    member.type = tarfile.REGTYPE
                    member.size = info.st_size
                    member.mode = _file_mode(info.st_mode)

                    with path.open("rb") as stream:
                        archive.addfile(member, stream)
                else:
                    raise WorkspaceViolation(
                        f"special file not allowed: {relative}"
                    )

    return buffer.getvalue()


def _assert_no_symlink_parents(destination: Path, relative: PurePosixPath) -> None:
    current = destination

    for part in relative.parts[:-1]:
        current = current / part

        if current.is_symlink():
            raise WorkspaceViolation(
                f"write through symlink: {relative}"
            )


def extract_workspace(
    archive: bytes,
    destination: Path,
    limits: WorkspaceLimits = WorkspaceLimits(),
) -> list[str]:
    """Extract an archive returned by a guest into an empty directory.

    Rejects absolute paths, ``..``, hardlinks, device files, FIFOs,
    symlinks that leave the destination and writes through symlinks.
    Validation happens for every member before anything is written.
    """

    destination = Path(destination)

    if not destination.is_dir() or destination.is_symlink():
        raise WorkspaceViolation(f"not a real directory: {destination}")

    if any(destination.iterdir()):
        raise WorkspaceViolation(f"destination not empty: {destination}")

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:*") as source:
        members = source.getmembers()

        if len(members) > limits.max_entries:
            raise WorkspaceViolation(
                f"archive has more than {limits.max_entries} entries"
            )

        planned: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
        seen: set[PurePosixPath] = set()
        total = 0

        for member in members:
            relative = _safe_relative(member.name)

            if relative in seen:
                raise WorkspaceViolation(f"duplicate member: {relative}")

            seen.add(relative)

            if member.isreg():
                if member.size > limits.max_file_bytes:
                    raise WorkspaceViolation(f"file too large: {relative}")

                total += member.size

                if total > limits.max_total_bytes:
                    raise WorkspaceViolation("archive exceeds size limit")
            elif member.issym():
                if not _symlink_stays_inside(relative, member.linkname):
                    raise WorkspaceViolation(
                        f"symlink leaves workspace: {relative} -> {member.linkname}"
                    )
            elif member.islnk():
                raise WorkspaceViolation(f"hardlink not allowed: {relative}")
            elif not member.isdir():
                raise WorkspaceViolation(
                    f"special file not allowed: {relative}"
                )

            planned.append((member, relative))

        symlinks = {
            relative for member, relative in planned if member.issym()
        }

        for _, relative in planned:
            for parent in relative.parents:
                if parent in symlinks:
                    raise WorkspaceViolation(
                        f"member nested under symlink: {relative}"
                    )

        # Directories first, then files, then symlinks last, so no file
        # is ever written through a symlink created by the same archive.
        order = {tarfile.DIRTYPE: 0, tarfile.SYMTYPE: 2}
        planned.sort(key=lambda item: (order.get(item[0].type, 1), str(item[1])))

        written: list[str] = []

        for member, relative in planned:
            target = destination.joinpath(*relative.parts)
            _assert_no_symlink_parents(destination, relative)

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
            elif member.isreg():
                target.parent.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
                extracted = source.extractfile(member)

                if extracted is None:
                    raise WorkspaceViolation(f"unreadable member: {relative}")

                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    _file_mode(member.mode),
                )

                with os.fdopen(descriptor, "wb") as stream:
                    while chunk := extracted.read(1024 * 1024):
                        stream.write(chunk)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
                os.symlink(member.linkname, target)

            written.append(relative.as_posix())

    return written


@dataclass(slots=True)
class WorkspaceLease:
    path: Path
    _closed: bool = False

    @classmethod
    def create(
        cls,
        *,
        root: Path | None = None,
        prefix: str = "dataworc-workspace-",
    ) -> "WorkspaceLease":
        import tempfile

        directory = Path(
            tempfile.mkdtemp(
                prefix=prefix,
                dir=root,
            )
        )

        directory.chmod(0o700)

        return cls(
            path=directory,
        )

    def close(self) -> None:
        import shutil

        if self._closed:
            return

        shutil.rmtree(
            self.path,
            ignore_errors=False,
        )

        if self.path.exists():
            raise RuntimeError(
                "workspace survived cleanup: "
                f"{self.path}"
            )

        self._closed = True

    def __enter__(self) -> "WorkspaceLease":
        return self

    def __exit__(
        self,
        *_: object,
    ) -> None:
        self.close()
