from pathlib import Path

import pytest

from engine.sandbox import selector
from engine.sandbox.models import (
    IsolationClass,
    RuntimeCapability,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.selector import (
    SandboxRuntimeUnavailable,
    select_runtime,
)


def test_host_os_request_selects_podman(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        selector,
        "discover_runtimes",
        lambda: (
            RuntimeCapability(
                runtime_kind=RuntimeKind.PODMAN,
                isolation_class=IsolationClass.HOST_OS,
                available=True,
                executable=Path("/usr/bin/podman"),
            ),
        ),
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
    )

    result = select_runtime(request)

    assert result.runtime_kind == RuntimeKind.PODMAN
    assert result.isolation_class == IsolationClass.HOST_OS


def test_host_os_request_fails_when_podman_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        selector,
        "discover_runtimes",
        lambda: (
            RuntimeCapability(
                runtime_kind=RuntimeKind.PODMAN,
                isolation_class=IsolationClass.HOST_OS,
                available=False,
                executable=None,
                reason="podman executable not found",
            ),
        ),
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
    )

    with pytest.raises(
        SandboxRuntimeUnavailable,
        match="host_os",
    ):
        select_runtime(request)


def test_kernel_request_does_not_fall_back_to_podman(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        selector,
        "discover_runtimes",
        lambda: (
            RuntimeCapability(
                runtime_kind=RuntimeKind.PODMAN,
                isolation_class=IsolationClass.HOST_OS,
                available=True,
                executable=Path("/usr/bin/podman"),
            ),
            RuntimeCapability(
                runtime_kind=RuntimeKind.GVISOR,
                isolation_class=IsolationClass.KERNEL_EMULATION,
                available=False,
                executable=None,
                reason="runsc executable not found",
            ),
        ),
    )

    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=("python", "generated.py"),
    )

    with pytest.raises(
        SandboxRuntimeUnavailable,
        match="kernel_emulation",
    ):
        select_runtime(request)


def test_hardware_request_rejects_available_but_unimplemented_runtime(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        selector,
        "discover_runtimes",
        lambda: (
            RuntimeCapability(
                runtime_kind=RuntimeKind.QEMU_KVM,
                isolation_class=IsolationClass.HARDWARE,
                available=True,
                executable=Path(
                    "/usr/bin/qemu-system-x86_64"
                ),
            ),
        ),
    )

    request = SandboxRequest(
        workload_type=WorkloadType.BINARY,
        trust_level=TrustLevel.UNTRUSTED,
        command=("./binary",),
    )

    with pytest.raises(
        SandboxRuntimeUnavailable,
        match="runtime adapter not implemented",
    ):
        select_runtime(request)



def test_host_os_falls_back_to_incus_container_when_podman_unavailable(
    monkeypatch,
) -> None:
    from pathlib import Path

    from engine.sandbox.models import (
        IsolationClass,
        RuntimeCapability,
        RuntimeKind,
        SandboxRequest,
        TrustLevel,
        WorkloadType,
    )
    from engine.sandbox.selector import select_runtime

    capabilities = (
        RuntimeCapability(
            runtime_kind=RuntimeKind.PODMAN,
            isolation_class=IsolationClass.HOST_OS,
            available=False,
            executable=None,
            reason="podman unavailable",
        ),
        RuntimeCapability(
            runtime_kind=RuntimeKind.INCUS_CONTAINER,
            isolation_class=IsolationClass.HOST_OS,
            available=True,
            executable=Path("/usr/bin/incus"),
            reason=None,
        ),
    )

    monkeypatch.setattr(
        "engine.sandbox.selector.discover_runtimes",
        lambda: capabilities,
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("true",),
    )

    selection = select_runtime(request)

    assert selection.runtime_kind == RuntimeKind.INCUS_CONTAINER
    assert selection.isolation_class == IsolationClass.HOST_OS
