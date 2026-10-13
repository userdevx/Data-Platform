"""Build and verify the DataWorc Firecracker guest rootfs.

Task 09.4.

The pinned upstream rootfs is immutable.

A separate copy is edited with debugfs without mounting it and without
requiring root privileges.

The Task 09.4 manifest provides derived-build provenance and
self-consistency verification. Durable production image trust belongs
to the later Sandbox image registry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from firecracker_pins import (
    PinError,
    sha256_file,
)


GUEST_MANIFEST_SCHEMA = (
    "dataworc.sandbox."
    "firecracker_guest_image.v1"
)

AGENT_DIR = "/usr/local/lib/dataworc"

SERVICE_NAME = (
    "dataworc-firecracker-agent.service"
)

SERVICE_PATH = (
    f"/etc/systemd/system/{SERVICE_NAME}"
)

WANTS_DIR = (
    "/etc/systemd/system/"
    "multi-user.target.wants"
)

WANTS_LINK = (
    f"{WANTS_DIR}/{SERVICE_NAME}"
)

REQUIRED_EXECUTABLES = (
    "/usr/bin/python3",
    "/usr/bin/systemd-run",
    "/usr/bin/systemctl",
    "/sbin/init",
)


@dataclass(frozen=True)
class GuestFile:
    repo_path: str
    guest_path: str
    mode: int


GUEST_FILES = (
    GuestFile(
        (
            "engine/sandbox/images/guest/"
            "dataworc_guest_exec.py"
        ),
        (
            f"{AGENT_DIR}/"
            "dataworc_guest_exec.py"
        ),
        0o644,
    ),
    GuestFile(
        (
            "engine/sandbox/images/"
            "firecracker/guest/"
            "dataworc_firecracker_agent.py"
        ),
        (
            f"{AGENT_DIR}/"
            "dataworc_firecracker_agent.py"
        ),
        0o755,
    ),
    GuestFile(
        (
            "engine/sandbox/images/"
            "firecracker/guest/"
            f"{SERVICE_NAME}"
        ),
        SERVICE_PATH,
        0o644,
    ),
)


@dataclass(frozen=True)
class Inode:
    kind: str
    mode: int
    uid: int
    gid: int
    link_target: str | None


def _debugfs(
    image: Path,
    request: str,
    write: bool = False,
) -> str:
    argv = ["debugfs"]

    if write:
        argv.append("-w")

    argv += [
        "-R",
        request,
        str(image),
    ]

    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
    )

    return (
        completed.stdout
        + completed.stderr
    )


def stat_inode(
    image: Path,
    path: str,
) -> Inode | None:
    output = _debugfs(
        image,
        f'stat "{path}"',
    )

    kind = re.search(
        r"Type:\s+(\S+)",
        output,
    )

    if kind is None:
        return None

    mode = re.search(
        r"Mode:\s+0?([0-7]+)",
        output,
    )

    owner = re.search(
        (
            r"User:\s+(\d+)\s+"
            r"Group:\s+(\d+)"
        ),
        output,
    )

    link = re.search(
        r'Fast link dest:\s+"(.*)"',
        output,
    )

    return Inode(
        kind=kind.group(1),
        mode=(
            int(
                mode.group(1),
                8,
            )
            if mode
            else -1
        ),
        uid=(
            int(owner.group(1))
            if owner
            else -1
        ),
        gid=(
            int(owner.group(2))
            if owner
            else -1
        ),
        link_target=(
            link.group(1)
            if link
            else None
        ),
    )


def resolve_in_image(
    image: Path,
    path: str,
    max_hops: int = 8,
) -> tuple[str, Inode]:
    current = path

    for _ in range(max_hops):
        inode = stat_inode(
            image,
            current,
        )

        if inode is None:
            raise PinError(
                f"{path}: {current} "
                "not found in guest image"
            )

        if inode.kind != "symlink":
            return (
                current,
                inode,
            )

        if inode.link_target is None:
            raise PinError(
                f"{current}: unreadable "
                "symlink target"
            )

        target = PurePosixPath(
            inode.link_target
        )

        current = str(
            target
            if target.is_absolute()
            else (
                PurePosixPath(current).parent
                / target
            )
        )

    raise PinError(
        f"{path}: too many symlink hops"
    )


def dump_sha256(
    image: Path,
    path: str,
) -> str:
    with tempfile.TemporaryDirectory(
        prefix="dataworc-fc-dump-"
    ) as scratch:
        out = (
            Path(scratch)
            / "file"
        )

        _debugfs(
            image,
            f'dump "{path}" "{out}"',
        )

        if not out.is_file():
            raise PinError(
                f"could not read {path} "
                "from guest image"
            )

        return sha256_file(out)


def inputs_digest(
    base_rootfs_sha: str,
    repo_root: Path,
) -> tuple[str, list[dict]]:
    files: list[dict] = []

    digest = hashlib.sha256(
        base_rootfs_sha.encode()
    )

    for item in GUEST_FILES:
        source = (
            repo_root
            / item.repo_path
        )

        if not source.is_file():
            raise PinError(
                "guest source file missing: "
                f"{source}"
            )

        file_sha = sha256_file(
            source
        )

        digest.update(
            (
                f"{item.guest_path}\0"
                f"{item.mode:o}\0"
                f"{file_sha}\n"
            ).encode()
        )

        files.append(
            {
                "repo_path": (
                    item.repo_path
                ),
                "guest_path": (
                    item.guest_path
                ),
                "mode": (
                    f"{item.mode:04o}"
                ),
                "sha256": file_sha,
            }
        )

    return (
        digest.hexdigest(),
        files,
    )


def guest_image_dir(
    store: Path,
    arch: str,
    digest: str,
) -> Path:
    return (
        store.parent
        / (
            f"{arch}-dataworc-"
            f"{digest[:12]}"
        )
    )


def validate_image(
    image: Path,
    files: list[dict],
) -> dict:
    checks: dict = {}

    fsck = subprocess.run(
        [
            "e2fsck",
            "-fn",
            str(image),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if fsck.returncode != 0:
        raise PinError(
            "e2fsck reported problems:\n"
            f"{fsck.stdout}"
            f"{fsck.stderr}"
        )

    checks["e2fsck"] = "clean"

    for entry in files:
        inode = stat_inode(
            image,
            entry["guest_path"],
        )

        if (
            inode is None
            or inode.kind != "regular"
        ):
            raise PinError(
                f"{entry['guest_path']} "
                "missing or not a regular file"
            )

        if (
            inode.uid,
            inode.gid,
        ) != (
            0,
            0,
        ):
            raise PinError(
                f"{entry['guest_path']} "
                "not root:root "
                f"({inode.uid}:{inode.gid})"
            )

        if (
            f"{inode.mode:04o}"
            != entry["mode"]
        ):
            raise PinError(
                f"{entry['guest_path']} "
                f"mode {inode.mode:04o}, "
                f"expected {entry['mode']}"
            )

        if (
            dump_sha256(
                image,
                entry["guest_path"],
            )
            != entry["sha256"]
        ):
            raise PinError(
                f"{entry['guest_path']} "
                "content differs from repo file"
            )

    directory = stat_inode(
        image,
        AGENT_DIR,
    )

    if (
        directory is None
        or directory.kind != "directory"
        or (
            directory.uid,
            directory.gid,
        )
        != (
            0,
            0,
        )
    ):
        raise PinError(
            f"{AGENT_DIR} missing or "
            "not root-owned"
        )

    link = stat_inode(
        image,
        WANTS_LINK,
    )

    if (
        link is None
        or link.kind != "symlink"
        or link.link_target
        != SERVICE_PATH
    ):
        raise PinError(
            f"{WANTS_LINK} is not "
            f"a symlink to {SERVICE_PATH}"
        )

    checks["service_enabled"] = (
        WANTS_LINK
    )

    resolved: dict[str, str] = {}

    for executable in REQUIRED_EXECUTABLES:
        target, inode = (
            resolve_in_image(
                image,
                executable,
            )
        )

        if (
            inode.kind != "regular"
            or (
                inode.uid,
                inode.gid,
            )
            != (
                0,
                0,
            )
        ):
            raise PinError(
                f"{executable} -> {target} "
                "is not a root-owned "
                "regular file"
            )

        if not inode.mode & 0o111:
            raise PinError(
                f"{executable} -> {target} "
                "is not executable"
            )

        resolved[executable] = target

    checks["executables"] = resolved

    passwd = stat_inode(
        image,
        "/etc/passwd",
    )

    if (
        passwd is None
        or (
            passwd.uid,
            passwd.gid,
        )
        != (
            0,
            0,
        )
    ):
        raise PinError(
            "/etc/passwd is not root:root"
        )

    checks[
        "system_files_root_owned"
    ] = True

    return checks


def _install(
    image: Path,
    source: Path,
    guest_path: str,
    mode: int,
) -> None:
    if stat_inode(
        image,
        guest_path,
    ) is not None:
        raise PinError(
            f"{guest_path} already exists "
            "in the base image"
        )

    _debugfs(
        image,
        (
            f'write "{source}" '
            f'"{guest_path}"'
        ),
        write=True,
    )

    _debugfs(
        image,
        (
            f'sif "{guest_path}" '
            f'mode 0'
            f'{0o100000 | mode:o}'
        ),
        write=True,
    )

    _debugfs(
        image,
        f'sif "{guest_path}" uid 0',
        write=True,
    )

    _debugfs(
        image,
        f'sif "{guest_path}" gid 0',
        write=True,
    )


def _ensure_directory(
    image: Path,
    path: str,
) -> None:
    inode = stat_inode(
        image,
        path,
    )

    if inode is not None:
        if inode.kind != "directory":
            raise PinError(
                f"{path} exists but "
                "is not a directory"
            )

        return

    parent = str(
        PurePosixPath(path).parent
    )

    if parent != path:
        _ensure_directory(
            image,
            parent,
        )

    _debugfs(
        image,
        f'mkdir "{path}"',
        write=True,
    )

    _debugfs(
        image,
        f'sif "{path}" mode 040755',
        write=True,
    )

    _debugfs(
        image,
        f'sif "{path}" uid 0',
        write=True,
    )

    _debugfs(
        image,
        f'sif "{path}" gid 0',
        write=True,
    )


def build_image(
    base_rootfs: Path,
    base_rootfs_sha: str,
    output_dir: Path,
    repo_root: Path,
    provenance: dict,
) -> Path:
    """Build a distinct derived rootfs from the immutable base."""

    base_rootfs = (
        base_rootfs.resolve()
    )

    output_resolved = (
        output_dir.resolve(
            strict=False
        )
    )

    if (
        output_resolved
        == base_rootfs.parent
    ):
        raise PinError(
            "derived guest image directory "
            "must not be the pinned base "
            "rootfs directory"
        )

    if (
        output_resolved
        == base_rootfs
    ):
        raise PinError(
            "derived guest image path "
            "must not be the pinned "
            "base rootfs"
        )

    if output_dir.exists():
        raise PinError(
            "guest image already exists: "
            f"{output_dir} "
            "(verify it, or delete "
            "to rebuild)"
        )

    if (
        sha256_file(base_rootfs)
        != base_rootfs_sha
    ):
        raise PinError(
            "base rootfs does not match "
            "its pinned sha256"
        )

    digest, files = inputs_digest(
        base_rootfs_sha,
        repo_root,
    )

    partial = output_dir.with_name(
        output_dir.name + ".partial"
    )

    if partial.exists():
        shutil.rmtree(partial)

    partial.mkdir(
        parents=True,
        mode=0o755,
    )

    try:
        image = (
            partial
            / "rootfs.ext4"
        )

        shutil.copyfile(
            base_rootfs,
            image,
        )

        if (
            image.resolve()
            == base_rootfs
        ):
            raise PinError(
                "derived rootfs must not "
                "overwrite the pinned "
                "base rootfs"
            )

        if os.path.samefile(
            image,
            base_rootfs,
        ):
            raise PinError(
                "derived rootfs must not "
                "alias the pinned "
                "base rootfs"
            )

        os.chmod(
            image,
            0o644,
        )

        _ensure_directory(
            image,
            AGENT_DIR,
        )

        _ensure_directory(
            image,
            WANTS_DIR,
        )

        for item in GUEST_FILES:
            _install(
                image,
                (
                    repo_root
                    / item.repo_path
                ),
                item.guest_path,
                item.mode,
            )

        if stat_inode(
            image,
            WANTS_LINK,
        ) is not None:
            raise PinError(
                f"{WANTS_LINK} already "
                "exists in the base image"
            )

        _debugfs(
            image,
            (
                f'symlink '
                f'"{WANTS_LINK}" '
                f'"{SERVICE_PATH}"'
            ),
            write=True,
        )

        checks = validate_image(
            image,
            files,
        )

        os.chmod(
            image,
            0o444,
        )

        if (
            sha256_file(base_rootfs)
            != base_rootfs_sha
        ):
            raise PinError(
                "pinned base rootfs changed "
                "during derived image build"
            )

        checks[
            "base_rootfs_unchanged"
        ] = True

        checks[
            "derived_rootfs_separate"
        ] = True

        manifest = {
            "schema": (
                GUEST_MANIFEST_SCHEMA
            ),
            "built_at": (
                datetime.now(
                    timezone.utc
                ).isoformat(
                    timespec="seconds"
                )
            ),
            "inputs_sha256": digest,
            "base": {
                **provenance,
                "rootfs_sha256": (
                    base_rootfs_sha
                ),
            },
            "files": files,
            "symlinks": [
                {
                    "path": WANTS_LINK,
                    "target": (
                        SERVICE_PATH
                    ),
                }
            ],
            "rootfs": {
                "file": "rootfs.ext4",
                "sha256": (
                    sha256_file(image)
                ),
                "size_bytes": (
                    image.stat().st_size
                ),
            },
            "checks": checks,
            "trust": {
                "scope": (
                    "derived-build "
                    "provenance and "
                    "self-consistency"
                ),
                "durable_registry": (
                    "Task 11"
                ),
            },
            "builder": (
                _debugfs_version()
            ),
        }

        manifest_path = (
            partial
            / "manifest.json"
        )

        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        os.chmod(
            manifest_path,
            0o444,
        )

        partial.rename(
            output_dir
        )

    except BaseException:
        shutil.rmtree(
            partial,
            ignore_errors=True,
        )
        raise

    return output_dir


def verify_image(
    output_dir: Path,
    base_rootfs_sha: str,
    repo_root: Path,
) -> dict:
    manifest_path = (
        output_dir
        / "manifest.json"
    )

    if not manifest_path.is_file():
        raise PinError(
            "guest image manifest missing: "
            f"{manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if manifest.get(
        "schema"
    ) != GUEST_MANIFEST_SCHEMA:
        raise PinError(
            "unsupported guest manifest schema: "
            f"{manifest.get('schema')!r}"
        )

    if (
        manifest["base"][
            "rootfs_sha256"
        ]
        != base_rootfs_sha
    ):
        raise PinError(
            "guest image was built from "
            "a different base rootfs "
            "than the pin"
        )

    digest, files = inputs_digest(
        base_rootfs_sha,
        repo_root,
    )

    if (
        manifest["inputs_sha256"]
        != digest
        or manifest["files"]
        != files
    ):
        raise PinError(
            "guest image is stale: "
            "repo guest files changed "
            "since it was built"
        )

    image = (
        output_dir
        / manifest["rootfs"]["file"]
    )

    if not image.is_file():
        raise PinError(
            f"guest rootfs missing: {image}"
        )

    base_store = manifest.get(
        "base",
        {},
    ).get(
        "store"
    )

    if base_store is not None:
        candidate_base = (
            Path(base_store)
            .expanduser()
            / manifest["rootfs"]["file"]
        )

        if candidate_base.exists():
            if (
                image.resolve()
                == candidate_base.resolve()
            ):
                raise PinError(
                    "derived rootfs resolves "
                    "to the pinned base rootfs"
                )

            if os.path.samefile(
                image,
                candidate_base,
            ):
                raise PinError(
                    "derived rootfs aliases "
                    "the pinned base rootfs"
                )

    if (
        image.stat().st_mode
        & 0o222
    ):
        raise PinError(
            "guest rootfs is writable; "
            f"expected 0444: {image}"
        )

    if (
        sha256_file(image)
        != manifest["rootfs"][
            "sha256"
        ]
    ):
        raise PinError(
            "guest rootfs sha256 differs "
            "from its manifest"
        )

    validate_image(
        image,
        files,
    )

    return manifest


def _debugfs_version() -> str:
    completed = subprocess.run(
        [
            "debugfs",
            "-V",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    lines = (
        completed.stdout
        + completed.stderr
    ).strip().splitlines()

    return (
        lines[0]
        if lines
        else "unknown"
    )
