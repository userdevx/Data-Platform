"""Shared helpers for Firecracker pin generation and verification.

Imported by pin-firecracker.py (operator re-pin tool) and
verify-firecracker-pins.py (gate). Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
from pathlib import Path


PIN_SCHEMA = "dataworc.sandbox.firecracker_pin.v1"
PIN_FILE = Path("engine/sandbox/images/firecracker/pinned.json")
STORE_ROOT = "~/.local/share/dataworc/sandbox/images/firecracker"
RELEASE_URL = (
    "https://github.com/firecracker-microvm/firecracker/releases/download"
)

_VERSION = re.compile(r"\b(?:Firecracker|Jailer)\s+v(\d+\.\d+\.\d+)\b")


class PinError(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(f"FAIL: {message}")


def host_arch() -> str:
    machine = platform.machine()
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def resolve_executable(name: str) -> Path:
    found = shutil.which(name)

    if not found:
        raise PinError(f"required executable not found: {name}")

    path = Path(found).resolve()

    if not path.is_file():
        raise PinError(f"executable is not a regular file: {path}")

    return path


def require_root_owned_not_writable(path: Path) -> None:
    """A pinned binary that the user (or anyone) can rewrite is not a
    trust anchor: re-hashing it only proves it was not changed *yet*."""

    info = path.stat()

    if info.st_uid != 0:
        raise PinError(f"{path} is not owned by root (uid={info.st_uid})")

    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PinError(f"{path} is writable by group or others")


def binary_version(path: Path) -> str:
    """Semantic version from ``--version``.

    Firecracker also prints a timestamped log line on exit, so the raw
    output differs on every run; only the version number is compared.
    """

    completed = subprocess.run(
        [str(path), "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    if completed.returncode != 0:
        raise PinError(
            f"{path} --version returned {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )

    match = _VERSION.search(completed.stdout + "\n" + completed.stderr)

    if match is None:
        raise PinError(
            f"no version found in {path} --version output: "
            f"{(completed.stdout + completed.stderr).strip()[:200]!r}"
        )

    return match.group(1)


def store_dir(ci_artifact_id: str, arch: str) -> Path:
    return Path(STORE_ROOT).expanduser() / ci_artifact_id / arch


def read_manifest(path: Path) -> dict:
    """Read the manifest written by fetch-firecracker-artifacts.sh."""

    if not path.is_file():
        raise PinError(f"external manifest missing: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("schema") != "dataworc.sandbox.firecracker_image.v1":
        raise PinError(f"unsupported manifest schema: {data.get('schema')!r}")

    try:
        data["kernel"]["sha256"]
        data["rootfs_ext4"]["sha256"]
        data["ci_artifact_prefix"]
    except (KeyError, TypeError) as exc:
        raise PinError(f"manifest lacks required field: {exc}") from exc

    return data


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
