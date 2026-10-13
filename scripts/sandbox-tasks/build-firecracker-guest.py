#!/usr/bin/env python3
"""Build or verify the DataWorc Firecracker guest image.

Task 09.4.

Build:
    python scripts/sandbox-tasks/build-firecracker-guest.py

Verify only:
    python scripts/sandbox-tasks/build-firecracker-guest.py --verify
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent
    ),
)

from firecracker_guest_image import (  # noqa: E402
    build_image,
    guest_image_dir,
    inputs_digest,
    verify_image,
)

from firecracker_pins import (  # noqa: E402
    PIN_FILE,
    PinError,
    sha256_file,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify only; never build",
    )

    args = parser.parse_args()

    repo_root = Path.cwd()

    if not PIN_FILE.is_file():
        raise PinError(
            f"pin file missing: {PIN_FILE}; "
            "run from repository root"
        )

    pin = json.loads(
        PIN_FILE.read_text(
            encoding="utf-8"
        )
    )

    artifacts = pin["artifacts"]

    store = Path(
        artifacts["store"]
    ).expanduser()

    base_rootfs = (
        store
        / artifacts["rootfs"]["file"]
    )

    base_sha = (
        artifacts["rootfs"]["sha256"]
    )

    if (
        sha256_file(base_rootfs)
        != base_sha
    ):
        raise PinError(
            "pinned base rootfs changed "
            f"on disk: {base_rootfs}"
        )

    digest, _ = inputs_digest(
        base_sha,
        repo_root,
    )

    output_dir = guest_image_dir(
        store,
        pin["architecture"],
        digest,
    )

    print(
        f"guest_image_dir={output_dir}"
    )

    if not output_dir.exists():
        if args.verify:
            raise PinError(
                "guest image not built for "
                f"current inputs: {output_dir}"
            )

        print(
            "building derived guest image"
        )

        build_image(
            base_rootfs,
            base_sha,
            output_dir,
            repo_root,
            provenance={
                "ci_artifact_id": (
                    artifacts[
                        "ci_artifact_id"
                    ]
                ),
                "pin_file": str(
                    PIN_FILE
                ),
                "kernel_sha256": (
                    artifacts[
                        "kernel"
                    ][
                        "sha256"
                    ]
                ),
                "store": str(store),
            },
        )

        print(
            "PASS: built guest image"
        )

    manifest = verify_image(
        output_dir,
        base_sha,
        repo_root,
    )

    for entry in manifest["files"]:
        print(
            "PASS: "
            f"{entry['guest_path']} "
            f"{entry['mode']} "
            "root:root "
            "sha256 "
            f"{entry['sha256'][:16]}"
        )

    for path, target in (
        manifest[
            "checks"
        ][
            "executables"
        ].items()
    ):
        print(
            f"PASS: {path} -> {target}"
        )

    print(
        "PASS: service enabled via "
        f"{manifest['checks']['service_enabled']}"
    )

    print(
        "PASS: e2fsck clean"
    )

    print(
        "PASS: base rootfs unchanged"
    )

    print(
        "PASS: derived rootfs separate "
        "from pinned base"
    )

    derived = (
        output_dir
        / manifest["rootfs"]["file"]
    )

    print(
        "PASS: guest rootfs read-only, "
        "sha256 "
        f"{sha256_file(derived)}"
    )

    print(
        "PASS: base rootfs "
        f"{base_sha[:16]} unchanged "
        "(pinned)"
    )

    print(
        "PASS: derived image trust scope "
        "is build provenance/self-consistency; "
        "durable registry is Task 11"
    )

    print(
        "PASS: TASK 09.4"
    )


if __name__ == "__main__":
    main()
