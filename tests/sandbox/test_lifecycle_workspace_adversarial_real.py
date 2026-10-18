from __future__ import annotations

import io
import os
import tarfile
from pathlib import Path

import pytest

from engine.sandbox.lifecycle.workspace import (
    WorkspaceLimits,
    WorkspaceViolation,
    extract_workspace,
    pack_workspace,
)


def _archive(
    members: list[tuple[tarfile.TarInfo, bytes | None]],
) -> bytes:
    buffer = io.BytesIO()

    with tarfile.open(
        fileobj=buffer,
        mode="w",
        format=tarfile.PAX_FORMAT,
    ) as archive:
        for member, payload in members:
            if payload is None:
                archive.addfile(member)
            else:
                member.size = len(payload)
                archive.addfile(
                    member,
                    io.BytesIO(payload),
                )

    return buffer.getvalue()


def _file(
    name: str,
    payload: bytes = b"x",
) -> tuple[tarfile.TarInfo, bytes]:
    member = tarfile.TarInfo(name)
    member.mode = 0o644

    return member, payload


def _directory(
    name: str,
) -> tuple[tarfile.TarInfo, None]:
    member = tarfile.TarInfo(name)
    member.type = tarfile.DIRTYPE
    member.mode = 0o755

    return member, None


def _symlink(
    name: str,
    target: str,
) -> tuple[tarfile.TarInfo, None]:
    member = tarfile.TarInfo(name)
    member.type = tarfile.SYMTYPE
    member.linkname = target
    member.mode = 0o777

    return member, None


def test_extract_rejects_absolute_path(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _file(
                "/outside.txt",
                b"escape",
            ),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
        match="absolute path",
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_ABSOLUTE_PATH_REJECTED_OK"
    )


def test_extract_rejects_parent_traversal(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    outside = tmp_path / "outside.txt"

    archive = _archive(
        [
            _file(
                "../outside.txt",
                b"escape",
            ),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
        match="parent traversal",
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert not outside.exists()
    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_PARENT_TRAVERSAL_REJECTED_OK"
    )


def test_extract_rejects_hardlink(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    regular, payload = _file(
        "original.txt",
        b"original",
    )

    hardlink = tarfile.TarInfo(
        "hardlink.txt"
    )
    hardlink.type = tarfile.LNKTYPE
    hardlink.linkname = "original.txt"

    archive = _archive(
        [
            (regular, payload),
            (hardlink, None),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_HARDLINK_REJECTED_OK"
    )


def test_extract_rejects_escaping_symlink(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _symlink(
                "escape",
                "../../outside",
            ),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_ESCAPING_SYMLINK_REJECTED_OK"
    )


def test_extract_rejects_file_nested_under_symlink(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _directory("real"),
            _symlink(
                "alias",
                "real",
            ),
            _file(
                "alias/through-link.txt",
                b"must-not-write",
            ),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_SYMLINK_PARENT_WRITE_REJECTED_OK"
    )


def test_extract_rejects_character_device(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    device = tarfile.TarInfo(
        "device"
    )
    device.type = tarfile.CHRTYPE
    device.devmajor = 1
    device.devminor = 3

    archive = _archive(
        [
            (device, None),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_DEVICE_FILE_REJECTED_OK"
    )


def test_extract_rejects_duplicate_member(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _file(
                "duplicate.txt",
                b"first",
            ),
            _file(
                "duplicate.txt",
                b"second",
            ),
        ]
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_DUPLICATE_MEMBER_REJECTED_OK"
    )


def test_extract_enforces_entry_limit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _file("one.txt"),
            _file("two.txt"),
        ]
    )

    limits = WorkspaceLimits(
        max_entries=1,
        max_total_bytes=1024,
        max_file_bytes=1024,
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
            limits,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_ENTRY_QUOTA_REJECTED_OK"
    )


def test_extract_enforces_per_file_limit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _file(
                "large.txt",
                b"12345",
            ),
        ]
    )

    limits = WorkspaceLimits(
        max_entries=10,
        max_total_bytes=1024,
        max_file_bytes=4,
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
            limits,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_FILE_QUOTA_REJECTED_OK"
    )


def test_extract_enforces_total_size_limit(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    archive = _archive(
        [
            _file(
                "one.txt",
                b"123",
            ),
            _file(
                "two.txt",
                b"456",
            ),
        ]
    )

    limits = WorkspaceLimits(
        max_entries=10,
        max_total_bytes=5,
        max_file_bytes=4,
    )

    with pytest.raises(
        WorkspaceViolation,
    ):
        extract_workspace(
            archive,
            destination,
            limits,
        )

    assert list(destination.iterdir()) == []

    print(
        "WORKSPACE_TOTAL_QUOTA_REJECTED_OK"
    )


def test_real_workspace_round_trip(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"

    source.mkdir()
    destination.mkdir()

    directory = source / "project"
    directory.mkdir()

    executable = directory / "run.sh"
    executable.write_text(
        "#!/bin/sh\n"
        "printf 'WORKSPACE_OK\\n'\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    data = directory / "data.txt"
    data.write_text(
        "real workspace data\n",
        encoding="utf-8",
    )

    link = source / "data-link"
    os.symlink(
        "project/data.txt",
        link,
    )

    archive = pack_workspace(
        source,
    )

    extracted = extract_workspace(
        archive,
        destination,
    )

    assert (
        destination
        / "project"
        / "data.txt"
    ).read_text(
        encoding="utf-8",
    ) == "real workspace data\n"

    assert (
        destination
        / "project"
        / "run.sh"
    ).stat().st_mode & 0o111

    restored_link = (
        destination
        / "data-link"
    )

    assert restored_link.is_symlink()
    assert os.readlink(
        restored_link
    ) == "project/data.txt"

    assert extracted

    print(
        "REAL_WORKSPACE_ROUND_TRIP_OK"
    )
