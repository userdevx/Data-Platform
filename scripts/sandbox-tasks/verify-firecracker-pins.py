#!/usr/bin/env python3
"""Verify Firecracker binaries and guest artifacts against pinned.json.

Used by the Task 9 gate on every run. Offline; never rewrites pins.
Prints "PASS: TASK 09.2" only if every check passes.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from firecracker_pins import (  # noqa: E402
    PIN_FILE,
    PIN_SCHEMA,
    PinError,
    binary_version,
    host_arch,
    read_manifest,
    require_root_owned_not_writable,
    resolve_executable,
    sha256_file,
)


def check_hash(label: str, path: Path, expected: str) -> None:
    if not path.is_file():
        raise PinError(f"{label} missing: {path}")

    actual = sha256_file(path)

    if actual != expected:
        raise PinError(
            f"{label} sha256 mismatch\nexpected={expected}\nactual={actual}\npath={path}"
        )

    print(f"PASS: {label} sha256 {actual}")


def check_read_only(label: str, path: Path) -> None:
    if path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise PinError(f"{label} is writable; expected mode 0444: {path}")

    print(f"PASS: {label} is read-only")


def main() -> None:
    if not PIN_FILE.is_file():
        raise PinError(f"pin file missing: {PIN_FILE}")

    pins = json.loads(PIN_FILE.read_text(encoding="utf-8"))

    if pins.get("schema") != PIN_SCHEMA:
        raise PinError(f"unsupported pin schema: {pins.get('schema')!r}")

    if host_arch() != pins["architecture"]:
        raise PinError(
            f"architecture mismatch: host={host_arch()} pinned={pins['architecture']}"
        )

    print(f"PASS: architecture {pins['architecture']}")

    for name in ("firecracker", "jailer"):
        pinned = pins[name]
        path = resolve_executable(name)

        if str(path) != pinned["path"]:
            raise PinError(f"{name} resolves to {path}, pinned {pinned['path']}")

        require_root_owned_not_writable(path)
        version = binary_version(path)

        if version != pinned["version"]:
            raise PinError(f"{name} version v{version}, pinned v{pinned['version']}")

        print(f"PASS: {name} version v{version}")
        check_hash(name, path, pinned["sha256"])

    artifacts = pins["artifacts"]
    store = Path(artifacts["store"]).expanduser()
    manifest_path = store / "manifest.json"

    check_hash("external manifest", manifest_path, artifacts["manifest_sha256"])
    manifest = read_manifest(manifest_path)

    for key, manifest_key in (("kernel", "kernel"), ("rootfs", "rootfs_ext4")):
        pinned = artifacts[key]
        path = store / pinned["file"]

        check_hash(f"Firecracker {key}", path, pinned["sha256"])
        check_read_only(f"Firecracker {key}", path)

        if manifest[manifest_key]["sha256"] != pinned["sha256"]:
            raise PinError(f"external manifest {key} hash differs from repo pin")

    print("PASS: external manifest agrees with repo pins")
    print("PASS: TASK 09.2")


if __name__ == "__main__":
    main()
