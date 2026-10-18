#!/usr/bin/env python3
"""Create engine/sandbox/images/firecracker/pinned.json (Task 9.2).

Operator tool. Run it only when deliberately (re)pinning; the gate uses
verify-firecracker-pins.py and never regenerates pins.

Trust chain recorded in the pin:
  1. Official release tarball  -> its published .sha256.txt matches
  2. Binaries inside tarball   -> byte-identical to installed binaries
  3. External manifest          -> kernel/rootfs hashes match files on disk

Usage:
  python scripts/sandbox-tasks/pin-firecracker.py \
      --ci-artifact-id 20261008-40f3a4819490-0

  # offline: use already-downloaded release assets
  python scripts/sandbox-tasks/pin-firecracker.py \
      --ci-artifact-id 20261008-40f3a4819490-0 --release-dir ~/Downloads
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from firecracker_pins import (  # noqa: E402
    PIN_FILE,
    PIN_SCHEMA,
    RELEASE_URL,
    STORE_ROOT,
    PinError,
    binary_version,
    host_arch,
    read_manifest,
    require_root_owned_not_writable,
    resolve_executable,
    sha256_file,
    store_dir,
    write_json_atomic,
)


def fetch_release_assets(
    version: str,
    arch: str,
    release_dir: Path | None,
    work: Path,
) -> tuple[Path, str, str]:
    name = f"firecracker-v{version}-{arch}.tgz"
    checksum_name = f"{name}.sha256.txt"
    url = f"{RELEASE_URL}/v{version}/{name}"

    if release_dir is not None:
        tarball = release_dir / name
        checksum_file = release_dir / checksum_name

        if not tarball.is_file() or not checksum_file.is_file():
            raise PinError(f"missing {name} or {checksum_name} in {release_dir}")
    else:
        tarball = work / name
        checksum_file = work / checksum_name

        for source, target in ((url, tarball), (f"{url}.sha256.txt", checksum_file)):
            print(f"download {source}")
            with urllib.request.urlopen(source, timeout=60) as response:
                target.write_bytes(response.read())

    published = checksum_file.read_text(encoding="utf-8").split()

    if not published or len(published[0]) != 64:
        raise PinError(f"unreadable checksum file: {checksum_file}")

    actual = sha256_file(tarball)

    if actual != published[0].lower():
        raise PinError(
            f"release tarball sha256 mismatch\npublished={published[0]}\nactual={actual}"
        )

    print(f"PASS: release tarball matches published sha256 {actual}")
    return tarball, actual, url


def extract_release_binary(tarball: Path, member_name: str, work: Path) -> Path:
    with tarfile.open(tarball, "r:gz") as archive:
        try:
            member = archive.getmember(member_name)
        except KeyError as exc:
            raise PinError(f"{member_name} not found in {tarball.name}") from exc

        if not member.isreg():
            raise PinError(f"{member_name} is not a regular file in the tarball")

        source = archive.extractfile(member)
        target = work / Path(member_name).name
        target.write_bytes(source.read())

    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci-artifact-id", required=True)
    parser.add_argument("--release-dir", type=Path)
    args = parser.parse_args()

    arch = host_arch()

    if arch not in {"x86_64", "aarch64"}:
        raise PinError(f"unsupported host architecture: {arch}")

    firecracker = resolve_executable("firecracker")
    jailer = resolve_executable("jailer")
    require_root_owned_not_writable(firecracker)
    require_root_owned_not_writable(jailer)

    version = binary_version(firecracker)
    jailer_version = binary_version(jailer)

    if version != jailer_version:
        raise PinError(f"firecracker v{version} and jailer v{jailer_version} differ")

    with tempfile.TemporaryDirectory(prefix="dataworc-fc-pin-") as scratch:
        work = Path(scratch)
        tarball, tarball_sha, url = fetch_release_assets(
            version, arch, args.release_dir, work
        )

        release = f"release-v{version}-{arch}"
        binaries = {}

        for name, installed in (("firecracker", firecracker), ("jailer", jailer)):
            official = extract_release_binary(
                tarball, f"{release}/{name}-v{version}-{arch}", work
            )
            official_sha = sha256_file(official)
            installed_sha = sha256_file(installed)

            if official_sha != installed_sha:
                raise PinError(
                    f"installed {name} is not the official v{version} binary\n"
                    f"official={official_sha}\ninstalled={installed_sha}\npath={installed}"
                )

            print(f"PASS: installed {name} == official release binary {installed_sha}")
            binaries[name] = {
                "version": version,
                "sha256": installed_sha,
                "path": str(installed),
            }

    store = store_dir(args.ci_artifact_id, arch)
    manifest_path = store / "manifest.json"
    manifest = read_manifest(manifest_path)

    if not manifest["ci_artifact_prefix"].rstrip("/").endswith(args.ci_artifact_id):
        raise PinError(
            f"manifest belongs to {manifest['ci_artifact_prefix']!r}, "
            f"not {args.ci_artifact_id!r}"
        )

    artifacts = {}

    for key, manifest_key, filename in (
        ("kernel", "kernel", "vmlinux"),
        ("rootfs", "rootfs_ext4", "rootfs.ext4"),
    ):
        path = store / filename

        if not path.is_file():
            raise PinError(f"artifact missing: {path}")

        actual = sha256_file(path)
        expected = manifest[manifest_key]["sha256"]

        if actual != expected:
            raise PinError(
                f"{filename} does not match external manifest\n"
                f"manifest={expected}\nactual={actual}"
            )

        print(f"PASS: {filename} matches external manifest {actual}")
        artifacts[key] = {"file": filename, "sha256": actual}

    pin = {
        "schema": PIN_SCHEMA,
        "architecture": arch,
        "pinned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "firecracker": binaries["firecracker"],
        "jailer": binaries["jailer"],
        "release": {
            "url": url,
            "tarball_sha256": tarball_sha,
        },
        "artifacts": {
            "ci_artifact_id": args.ci_artifact_id,
            "store": f"{STORE_ROOT}/{args.ci_artifact_id}/{arch}",
            "manifest_sha256": sha256_file(manifest_path),
            "kernel_version": manifest["kernel"].get("version"),
            "ubuntu_version": manifest.get("rootfs_upstream", {}).get("ubuntu_version"),
            "kernel": artifacts["kernel"],
            "rootfs": artifacts["rootfs"],
        },
    }

    write_json_atomic(PIN_FILE, pin)
    print(f"PASS: wrote {PIN_FILE}")


if __name__ == "__main__":
    main()
