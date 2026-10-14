from __future__ import annotations

import json
from pathlib import Path

from engine.sandbox.models import IsolationClass, RuntimeKind
from engine.sandbox.runtime.firecracker import (
    FirecrackerRuntime,
)

from .models import ArtifactDescriptor, RuntimeDescriptor
from .registry import RegistryError, RuntimeImageRegistry


_ARTIFACT_BINARY = "firecracker.binary"
_ARTIFACT_KERNEL = "firecracker.kernel"
_ARTIFACT_BASE_ROOTFS = "firecracker.base_rootfs"
_ARTIFACT_GUEST_ROOTFS = "firecracker.guest_rootfs"


def _read_pin(pin_file: Path) -> dict:
    try:
        value = json.loads(
            Path(pin_file).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(
            f"unable to read Firecracker pin: {pin_file}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise RegistryError(
            f"Firecracker pin must contain a JSON object: {pin_file}"
        )

    return value


def load_firecracker_registry(
    *,
    pin_file: Path,
    repo_root: Path | None = None,
    guest_image_override: Path | None = None,
) -> RuntimeImageRegistry:
    """Build a registry from the existing Task 09 Firecracker authority.

    Paths and digests come from the supplied tracked pin and guest manifest.
    No machine-specific artifact path or digest is embedded here.
    """

    runtime_kwargs: dict[str, object] = {
        "pin_file": Path(pin_file),
    }

    if repo_root is not None:
        runtime_kwargs["repo_root"] = Path(repo_root)

    if guest_image_override is not None:
        runtime_kwargs["guest_image_override"] = Path(
            guest_image_override
        )

    runtime = FirecrackerRuntime(**runtime_kwargs)

    # Task 09 authority validates pin schema, architecture, executable
    # ownership, pinned executable/kernel state, guest-manifest provenance,
    # source-input digest, and derived-image relationship.
    resolved = runtime.resolve_artifacts()

    pin = _read_pin(Path(pin_file))

    try:
        artifact_config = pin["artifacts"]

        store = Path(
            artifact_config["store"]
        ).expanduser()

        base_rootfs = (
            store
            / artifact_config["rootfs"]["file"]
        )

        base_rootfs_sha = artifact_config["rootfs"]["sha256"]
        kernel_sha = artifact_config["kernel"]["sha256"]
        binary_sha = pin["firecracker"]["sha256"]
    except (KeyError, TypeError) as exc:
        raise RegistryError(
            f"Firecracker pin lacks required registry field: {exc}"
        ) from exc

    registry = RuntimeImageRegistry()

    registry.register_artifact(
        ArtifactDescriptor(
            name=_ARTIFACT_BINARY,
            path=resolved.firecracker,
            sha256=binary_sha,
            owner_uid=0,
            metadata={
                "source": "firecracker_pin",
                "role": "runtime_binary",
            },
        )
    )

    registry.register_artifact(
        ArtifactDescriptor(
            name=_ARTIFACT_KERNEL,
            path=resolved.kernel,
            sha256=kernel_sha,
            require_read_only=True,
            metadata={
                "source": "firecracker_pin",
                "role": "guest_kernel",
            },
        )
    )

    registry.register_artifact(
        ArtifactDescriptor(
            name=_ARTIFACT_BASE_ROOTFS,
            path=base_rootfs,
            sha256=base_rootfs_sha,
            require_read_only=True,
            metadata={
                "source": "firecracker_pin",
                "role": "base_rootfs",
            },
        )
    )

    registry.register_artifact(
        ArtifactDescriptor(
            name=_ARTIFACT_GUEST_ROOTFS,
            path=resolved.rootfs,
            sha256=resolved.rootfs_sha256,
            require_read_only=True,
            metadata={
                "source": "firecracker_guest_manifest",
                "role": "derived_guest_rootfs",
            },
        )
    )

    registry.register_runtime(
        RuntimeDescriptor(
            runtime_kind=RuntimeKind.FIRECRACKER.value,
            isolation_class=IsolationClass.HARDWARE.value,
            implemented=True,
            artifacts=(
                _ARTIFACT_BINARY,
                _ARTIFACT_KERNEL,
                _ARTIFACT_BASE_ROOTFS,
                _ARTIFACT_GUEST_ROOTFS,
            ),
            metadata={
                "trust_authority": "task_09_firecracker_pin",
            },
        )
    )

    # The loader must never return a registry that merely describes files.
    # All registered Firecracker artifacts must actually verify.
    registry.assert_trusted(RuntimeKind.FIRECRACKER.value)

    return registry
