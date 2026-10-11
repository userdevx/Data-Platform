from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from engine.sandbox.models import (
    IsolationClass,
    RuntimeCapability,
    RuntimeKind,
)


KVM_DEVICE = Path("/dev/kvm")


def _find_executable(*names: str) -> Path | None:
    for name in names:
        resolved = shutil.which(name)

        if resolved is not None:
            return Path(resolved).resolve()

    return None


def has_kvm_access() -> bool:
    return (
        KVM_DEVICE.exists()
        and os.access(KVM_DEVICE, os.R_OK | os.W_OK)
    )


def discover_podman() -> RuntimeCapability:
    executable = _find_executable("podman")

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.PODMAN,
            isolation_class=IsolationClass.HOST_OS,
            available=False,
            executable=None,
            reason="podman executable not found",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.PODMAN,
        isolation_class=IsolationClass.HOST_OS,
        available=True,
        executable=executable,
    )


def discover_incus_container() -> RuntimeCapability:
    executable = _find_executable("incus")

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.INCUS_CONTAINER,
            isolation_class=IsolationClass.HOST_OS,
            available=False,
            executable=None,
            reason="incus executable not found",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.INCUS_CONTAINER,
        isolation_class=IsolationClass.HOST_OS,
        available=True,
        executable=executable,
    )


def discover_gvisor() -> RuntimeCapability:
    executable = _find_executable("runsc")

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.GVISOR,
            isolation_class=IsolationClass.KERNEL_EMULATION,
            available=False,
            executable=None,
            reason="runsc executable not found",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.GVISOR,
        isolation_class=IsolationClass.KERNEL_EMULATION,
        available=True,
        executable=executable,
    )


def discover_qemu_kvm() -> RuntimeCapability:
    machine = platform.machine().casefold()

    if machine in {"x86_64", "amd64"}:
        executable = _find_executable("qemu-system-x86_64")
    elif machine in {"aarch64", "arm64"}:
        executable = _find_executable("qemu-system-aarch64")
    else:
        executable = _find_executable(
            "qemu-system-x86_64",
            "qemu-system-aarch64",
        )

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.QEMU_KVM,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=None,
            reason="compatible QEMU system executable not found",
        )

    if not has_kvm_access():
        return RuntimeCapability(
            runtime_kind=RuntimeKind.QEMU_KVM,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason="/dev/kvm is not accessible",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.QEMU_KVM,
        isolation_class=IsolationClass.HARDWARE,
        available=True,
        executable=executable,
    )


def discover_incus_vm() -> RuntimeCapability:
    executable = _find_executable("incus")

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.INCUS_VM,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=None,
            reason="incus executable not found",
        )

    if not has_kvm_access():
        return RuntimeCapability(
            runtime_kind=RuntimeKind.INCUS_VM,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason="/dev/kvm is not accessible",
        )

    qemu = discover_qemu_kvm()

    if not qemu.available:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.INCUS_VM,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason=f"QEMU/KVM unavailable: {qemu.reason}",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.INCUS_VM,
        isolation_class=IsolationClass.HARDWARE,
        available=True,
        executable=executable,
    )


def discover_firecracker() -> RuntimeCapability:
    executable = _find_executable("firecracker")

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.FIRECRACKER,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=None,
            reason="firecracker executable not found",
        )

    jailer = _find_executable("jailer")

    if jailer is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.FIRECRACKER,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason="firecracker found but jailer executable not found",
        )

    if not has_kvm_access():
        return RuntimeCapability(
            runtime_kind=RuntimeKind.FIRECRACKER,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason="/dev/kvm is not accessible",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.FIRECRACKER,
        isolation_class=IsolationClass.HARDWARE,
        available=True,
        executable=executable,
    )


def discover_kata() -> RuntimeCapability:
    executable = _find_executable(
        "kata-runtime",
        "containerd-shim-kata-v2",
    )

    if executable is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.KATA,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=None,
            reason="Kata runtime executable not found",
        )

    if _find_executable("containerd") is None:
        return RuntimeCapability(
            runtime_kind=RuntimeKind.KATA,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason="Kata found but containerd executable not found",
        )

    if not has_kvm_access():
        return RuntimeCapability(
            runtime_kind=RuntimeKind.KATA,
            isolation_class=IsolationClass.HARDWARE,
            available=False,
            executable=executable,
            reason="/dev/kvm is not accessible",
        )

    return RuntimeCapability(
        runtime_kind=RuntimeKind.KATA,
        isolation_class=IsolationClass.HARDWARE,
        available=True,
        executable=executable,
    )


def discover_runtimes() -> tuple[RuntimeCapability, ...]:
    return (
        discover_podman(),
        discover_incus_container(),
        discover_gvisor(),
        discover_qemu_kvm(),
        discover_incus_vm(),
        discover_firecracker(),
        discover_kata(),
    )


def discover_containerd() -> Path | None:
    """
    Return containerd when available.

    containerd is supporting infrastructure, not a Sandbox RuntimeKind.
    """
    return _find_executable("containerd")
