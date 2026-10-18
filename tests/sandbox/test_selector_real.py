from __future__ import annotations

from pathlib import Path

import pytest

from engine.sandbox.discovery import discover_runtimes
from engine.sandbox.models import (
    IsolationClass,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.selector import (
    SandboxRuntimeUnavailable,
    select_runtime,
)


def _available() -> dict[RuntimeKind, bool]:
    return {
        capability.runtime_kind: capability.available
        for capability in discover_runtimes()
    }


def test_real_selector_host_os_prefers_podman() -> None:
    available = _available()

    assert available[RuntimeKind.PODMAN] is True

    request = SandboxRequest(
        workload_type=WorkloadType.TEST,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
    )

    selection = select_runtime(request)

    assert selection.isolation_class == IsolationClass.HOST_OS
    assert selection.runtime_kind == RuntimeKind.PODMAN

    print(
        "HOST_OS_SELECTOR_OK "
        f"runtime={selection.runtime_kind.value}"
    )


def test_real_selector_generated_code_uses_gvisor() -> None:
    available = _available()

    assert available[RuntimeKind.GVISOR] is True

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=("true",),
    )

    selection = select_runtime(request)

    assert (
        selection.isolation_class
        == IsolationClass.KERNEL_EMULATION
    )
    assert selection.runtime_kind == RuntimeKind.GVISOR

    print(
        "KERNEL_EMULATION_SELECTOR_OK "
        f"runtime={selection.runtime_kind.value}"
    )


def test_real_selector_vm_boundary_uses_available_hardware_runtime() -> None:
    available = _available()

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.UNTRUSTED,
        command=("true",),
        requires_vm_boundary=True,
    )

    selection = select_runtime(request)

    assert selection.isolation_class == IsolationClass.HARDWARE

    # Hardware runtimes that have a runtime adapter wired into the
    # selector. A runtime that is discovered on the host but has no
    # adapter must never be selected. Update this tuple when QEMU/KVM
    # and Kata are wired into the selector.
    implemented_hardware = (
        RuntimeKind.FIRECRACKER,
        RuntimeKind.INCUS_VM,
    )

    hardware_priority = (
        RuntimeKind.FIRECRACKER,
        RuntimeKind.INCUS_VM,
        RuntimeKind.QEMU_KVM,
        RuntimeKind.KATA,
    )

    expected = next(
        (
            runtime_kind
            for runtime_kind in hardware_priority
            if available.get(runtime_kind)
            and runtime_kind in implemented_hardware
        ),
        None,
    )

    assert expected is not None
    assert selection.runtime_kind == expected
    assert selection.runtime_kind in implemented_hardware

    print(
        "HARDWARE_SELECTOR_OK "
        f"runtime={selection.runtime_kind.value}"
    )


def test_real_selector_never_downgrades_generated_code() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=("true",),
    )

    selection = select_runtime(request)

    assert selection.runtime_kind != RuntimeKind.PODMAN
    assert selection.runtime_kind != RuntimeKind.INCUS_CONTAINER

    assert (
        selection.isolation_class
        == IsolationClass.KERNEL_EMULATION
    )

    print("NO_SECURITY_DOWNGRADE_OK")


def test_real_selector_hardware_skips_firecracker_for_workspace(
    tmp_path: Path,
) -> None:
    available = _available()

    assert available[RuntimeKind.FIRECRACKER] is True
    assert available[RuntimeKind.INCUS_VM] is True

    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.UNTRUSTED,
        command=("true",),
        working_directory=tmp_path,
        requires_vm_boundary=True,
    )

    selection = select_runtime(request)

    # Firecracker cannot transfer a host workspace; the request must
    # stay at hardware isolation on the next runtime, not downgrade.
    assert selection.isolation_class == IsolationClass.HARDWARE
    assert selection.runtime_kind == RuntimeKind.INCUS_VM

    print(
        "HARDWARE_WORKSPACE_FALLBACK_OK "
        f"runtime={selection.runtime_kind.value}"
    )


def test_real_selector_reports_firecracker_incompatibility() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.UNTRUSTED,
        command=("true",),
        network_enabled=True,
        requires_vm_boundary=True,
    )

    selection = select_runtime(request)

    assert selection.runtime_kind != RuntimeKind.FIRECRACKER
    assert selection.isolation_class == IsolationClass.HARDWARE

    print(
        "FIRECRACKER_NETWORK_SKIPPED_OK "
        f"runtime={selection.runtime_kind.value}"
    )
