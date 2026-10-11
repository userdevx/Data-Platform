from __future__ import annotations

from engine.sandbox.models import (
    IsolationClass,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)


HARDWARE_WORKLOADS = frozenset(
    {
        WorkloadType.BINARY,
        WorkloadType.INSTALLER,
        WorkloadType.SYSTEM,
    }
)

KERNEL_EMULATION_WORKLOADS = frozenset(
    {
        WorkloadType.SCRIPT,
        WorkloadType.USER_SCRIPT,
        WorkloadType.GENERATED_CODE,
    }
)


def required_isolation(request: SandboxRequest) -> IsolationClass:
    """
    Determine the minimum isolation boundary required for a sandbox request.

    This function is deterministic. Models and agents may submit execution
    requests, but they do not choose or weaken their own security boundary.
    """

    if request.requires_vm_boundary:
        return IsolationClass.HARDWARE

    if request.requires_kubernetes_runtime:
        return IsolationClass.HARDWARE

    if request.requires_full_system:
        if request.trust_level == TrustLevel.UNTRUSTED:
            return IsolationClass.HARDWARE

        return IsolationClass.HOST_OS

    if request.workload_type in HARDWARE_WORKLOADS:
        return IsolationClass.HARDWARE

    if request.trust_level == TrustLevel.UNTRUSTED:
        if request.workload_type in KERNEL_EMULATION_WORKLOADS:
            return IsolationClass.KERNEL_EMULATION

        return IsolationClass.HARDWARE

    if request.workload_type in KERNEL_EMULATION_WORKLOADS:
        return IsolationClass.KERNEL_EMULATION

    return IsolationClass.HOST_OS
