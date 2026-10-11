from __future__ import annotations

from engine.sandbox.discovery import discover_runtimes
from engine.sandbox.models import (
    IsolationClass,
    RuntimeCapability,
    RuntimeKind,
    SandboxRequest,
    SandboxSelection,
)
from engine.sandbox.policy.evaluator import required_isolation


class SandboxRuntimeUnavailable(RuntimeError):
    pass


_RUNTIME_PRIORITY: dict[IsolationClass, tuple[RuntimeKind, ...]] = {
    IsolationClass.HOST_OS: (
        RuntimeKind.PODMAN,
        RuntimeKind.INCUS_CONTAINER,
    ),
    IsolationClass.KERNEL_EMULATION: (
        RuntimeKind.GVISOR,
    ),
    IsolationClass.HARDWARE: (
        RuntimeKind.FIRECRACKER,
        RuntimeKind.INCUS_VM,
        RuntimeKind.QEMU_KVM,
        RuntimeKind.KATA,
    ),
}


_IMPLEMENTED_RUNTIMES = frozenset(
    {
        RuntimeKind.PODMAN,
        RuntimeKind.INCUS_CONTAINER,
        RuntimeKind.INCUS_VM,
    }
)


def _index_capabilities(
    capabilities: tuple[RuntimeCapability, ...],
) -> dict[RuntimeKind, RuntimeCapability]:
    return {
        capability.runtime_kind: capability
        for capability in capabilities
    }


def select_runtime(
    request: SandboxRequest,
) -> SandboxSelection:
    isolation_class = required_isolation(request)

    capabilities = _index_capabilities(
        discover_runtimes()
    )

    candidates = _RUNTIME_PRIORITY[isolation_class]

    unavailable_reasons: list[str] = []

    for runtime_kind in candidates:
        capability = capabilities.get(runtime_kind)

        if capability is None:
            unavailable_reasons.append(
                f"{runtime_kind.value}: not discovered"
            )
            continue

        if not capability.available:
            unavailable_reasons.append(
                f"{runtime_kind.value}: "
                f"{capability.reason or 'unavailable'}"
            )
            continue

        if runtime_kind not in _IMPLEMENTED_RUNTIMES:
            unavailable_reasons.append(
                f"{runtime_kind.value}: "
                "runtime adapter not implemented"
            )
            continue

        return SandboxSelection(
            isolation_class=isolation_class,
            runtime_kind=runtime_kind,
            reason=(
                f"{runtime_kind.value} selected for "
                f"{isolation_class.value} isolation"
            ),
        )

    details = "; ".join(unavailable_reasons)

    raise SandboxRuntimeUnavailable(
        f"No executable sandbox runtime available for "
        f"{isolation_class.value}"
        + (f": {details}" if details else "")
    )
