from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from engine.sandbox.models import RuntimeKind
from engine.sandbox.registry import (
    ArtifactDescriptor,
    ArtifactTrustError,
    RegistryError,
    RuntimeDescriptor,
    RuntimeImageRegistry,
    TrustStatus,
    load_firecracker_registry,
)
from engine.sandbox.runtime.firecracker import DEFAULT_PIN_FILE


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_registry_accepts_real_verified_file(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"dataworc-registry-real\n")
    artifact.chmod(0o444)

    registry = RuntimeImageRegistry()

    registry.register_artifact(
        ArtifactDescriptor(
            name="test-image",
            path=artifact,
            sha256=_digest(artifact.read_bytes()),
            size_bytes=artifact.stat().st_size,
            require_read_only=True,
        )
    )

    registry.register_runtime(
        RuntimeDescriptor(
            runtime_kind="test-runtime",
            isolation_class="hardware",
            implemented=True,
            artifacts=("test-image",),
        )
    )

    report = registry.verify_artifact("test-image")

    assert report.status is TrustStatus.TRUSTED
    registry.assert_trusted("test-runtime")


def test_registry_refuses_tampered_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"trusted")

    expected = _digest(artifact.read_bytes())
    artifact.write_bytes(b"tampered")

    registry = RuntimeImageRegistry()

    registry.register_artifact(
        ArtifactDescriptor(
            name="artifact",
            path=artifact,
            sha256=expected,
        )
    )

    with pytest.raises(ArtifactTrustError):
        registry.verify_artifact("artifact")


def test_registry_refuses_writable_trusted_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"trusted")
    artifact.chmod(0o644)

    registry = RuntimeImageRegistry()

    registry.register_artifact(
        ArtifactDescriptor(
            name="artifact",
            path=artifact,
            sha256=_digest(artifact.read_bytes()),
            require_read_only=True,
        )
    )

    with pytest.raises(ArtifactTrustError):
        registry.verify_artifact("artifact")


def test_registry_refuses_symlink(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.bin"
    link = tmp_path / "artifact.bin"

    target.write_bytes(b"trusted")
    link.symlink_to(target)

    registry = RuntimeImageRegistry()

    registry.register_artifact(
        ArtifactDescriptor(
            name="artifact",
            path=link,
            sha256=_digest(target.read_bytes()),
        )
    )

    report = registry.verify_artifact(
        "artifact",
        raise_on_failure=False,
    )

    assert report.status is TrustStatus.SYMLINK

    with pytest.raises(ArtifactTrustError):
        registry.verify_artifact("artifact")


def test_verify_runtime_reports_all_artifact_failures(
    tmp_path: Path,
) -> None:
    missing_one = tmp_path / "missing-one"
    missing_two = tmp_path / "missing-two"

    registry = RuntimeImageRegistry()

    registry.register_artifact(
        ArtifactDescriptor(
            name="one",
            path=missing_one,
            sha256="0" * 64,
        )
    )

    registry.register_artifact(
        ArtifactDescriptor(
            name="two",
            path=missing_two,
            sha256="1" * 64,
        )
    )

    registry.register_runtime(
        RuntimeDescriptor(
            runtime_kind="aggregate-test",
            isolation_class="hardware",
            implemented=True,
            artifacts=("one", "two"),
        )
    )

    reports = registry.verify_runtime("aggregate-test")

    assert len(reports) == 2
    assert all(
        report.status is TrustStatus.MISSING
        for report in reports
    )

    with pytest.raises(ArtifactTrustError) as captured:
        registry.assert_trusted("aggregate-test")

    message = str(captured.value)
    assert "missing-one" in message
    assert "missing-two" in message


def test_reserved_runtime_cannot_be_verified() -> None:
    registry = RuntimeImageRegistry()

    registry.register_runtime(
        RuntimeDescriptor(
            runtime_kind=RuntimeKind.KATA.value,
            isolation_class="hardware",
            implemented=False,
        )
    )

    with pytest.raises(RegistryError):
        registry.verify_runtime(RuntimeKind.KATA.value)


def test_real_firecracker_pin_loads_trusted_registry() -> None:
    registry = load_firecracker_registry(
        pin_file=DEFAULT_PIN_FILE,
    )

    runtime = registry.runtime(
        RuntimeKind.FIRECRACKER.value
    )

    assert runtime.implemented is True
    assert len(runtime.artifacts) == 4

    reports = registry.verify_runtime(
        RuntimeKind.FIRECRACKER.value
    )

    assert len(reports) == 4
    assert all(report.trusted for report in reports)

    registry.assert_trusted(
        RuntimeKind.FIRECRACKER.value
    )


def test_firecracker_registry_does_not_bless_qemu() -> None:
    registry = load_firecracker_registry(
        pin_file=DEFAULT_PIN_FILE,
    )

    with pytest.raises(RegistryError):
        registry.runtime(RuntimeKind.QEMU_KVM.value)
