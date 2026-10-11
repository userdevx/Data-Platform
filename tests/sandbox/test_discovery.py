from pathlib import Path

from engine.sandbox import discovery
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
)


def test_podman_available_when_executable_exists(monkeypatch) -> None:
    podman = Path("/usr/bin/podman")

    monkeypatch.setattr(
        discovery,
        "_find_executable",
        lambda *names: podman if "podman" in names else None,
    )

    result = discovery.discover_podman()

    assert result.runtime_kind == RuntimeKind.PODMAN
    assert result.isolation_class == IsolationClass.HOST_OS
    assert result.available is True
    assert result.executable == podman
    assert result.reason is None


def test_podman_unavailable_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        discovery,
        "_find_executable",
        lambda *names: None,
    )

    result = discovery.discover_podman()

    assert result.available is False
    assert result.executable is None
    assert result.reason == "podman executable not found"


def test_gvisor_requires_runsc(monkeypatch) -> None:
    monkeypatch.setattr(
        discovery,
        "_find_executable",
        lambda *names: None,
    )

    result = discovery.discover_gvisor()

    assert result.runtime_kind == RuntimeKind.GVISOR
    assert result.available is False
    assert result.reason == "runsc executable not found"


def test_qemu_requires_kvm_access(monkeypatch) -> None:
    qemu = Path("/usr/bin/qemu-system-x86_64")

    monkeypatch.setattr(
        discovery.platform,
        "machine",
        lambda: "x86_64",
    )
    monkeypatch.setattr(
        discovery,
        "_find_executable",
        lambda *names: qemu,
    )
    monkeypatch.setattr(
        discovery,
        "has_kvm_access",
        lambda: False,
    )

    result = discovery.discover_qemu_kvm()

    assert result.runtime_kind == RuntimeKind.QEMU_KVM
    assert result.available is False
    assert result.executable == qemu
    assert result.reason == "/dev/kvm is not accessible"


def test_qemu_available_with_binary_and_kvm(monkeypatch) -> None:
    qemu = Path("/usr/bin/qemu-system-x86_64")

    monkeypatch.setattr(
        discovery.platform,
        "machine",
        lambda: "x86_64",
    )
    monkeypatch.setattr(
        discovery,
        "_find_executable",
        lambda *names: qemu,
    )
    monkeypatch.setattr(
        discovery,
        "has_kvm_access",
        lambda: True,
    )

    result = discovery.discover_qemu_kvm()

    assert result.available is True
    assert result.executable == qemu


def test_firecracker_requires_jailer(monkeypatch) -> None:
    firecracker = Path("/usr/local/bin/firecracker")

    def fake_find(*names: str) -> Path | None:
        if "firecracker" in names:
            return firecracker
        return None

    monkeypatch.setattr(
        discovery,
        "_find_executable",
        fake_find,
    )

    result = discovery.discover_firecracker()

    assert result.available is False
    assert result.executable == firecracker
    assert (
        result.reason
        == "firecracker found but jailer executable not found"
    )


def test_kata_requires_containerd(monkeypatch) -> None:
    kata = Path("/usr/bin/containerd-shim-kata-v2")

    def fake_find(*names: str) -> Path | None:
        if (
            "kata-runtime" in names
            or "containerd-shim-kata-v2" in names
        ):
            return kata
        return None

    monkeypatch.setattr(
        discovery,
        "_find_executable",
        fake_find,
    )

    result = discovery.discover_kata()

    assert result.available is False
    assert result.executable == kata
    assert result.reason == "Kata found but containerd executable not found"


def test_discover_runtimes_returns_every_runtime_kind(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        discovery,
        "_find_executable",
        lambda *names: None,
    )

    results = discovery.discover_runtimes()

    assert {result.runtime_kind for result in results} == {
        RuntimeKind.PODMAN,
        RuntimeKind.INCUS_CONTAINER,
        RuntimeKind.GVISOR,
        RuntimeKind.QEMU_KVM,
        RuntimeKind.INCUS_VM,
        RuntimeKind.FIRECRACKER,
        RuntimeKind.KATA,
    }
