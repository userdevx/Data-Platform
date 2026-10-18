from engine.sandbox.models import (
    IsolationClass,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.policy.evaluator import required_isolation


def test_trusted_build_uses_host_os_isolation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("python", "--version"),
    )

    assert required_isolation(request) == IsolationClass.HOST_OS


def test_trusted_dependency_install_uses_host_os_isolation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.DEPENDENCY_INSTALL,
        trust_level=TrustLevel.TRUSTED,
        command=("python", "-m", "pip", "install", "example"),
    )

    assert required_isolation(request) == IsolationClass.HOST_OS


def test_generated_code_uses_kernel_emulation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.GENERATED_CODE,
        trust_level=TrustLevel.UNTRUSTED,
        command=("python", "generated.py"),
    )

    assert required_isolation(request) == IsolationClass.KERNEL_EMULATION


def test_user_script_uses_kernel_emulation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.USER_SCRIPT,
        trust_level=TrustLevel.UNTRUSTED,
        command=("python", "submitted.py"),
    )

    assert required_isolation(request) == IsolationClass.KERNEL_EMULATION


def test_unknown_binary_uses_hardware_isolation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.BINARY,
        trust_level=TrustLevel.UNTRUSTED,
        command=("./unknown-binary",),
    )

    assert required_isolation(request) == IsolationClass.HARDWARE


def test_installer_uses_hardware_isolation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.INSTALLER,
        trust_level=TrustLevel.LIMITED,
        command=("./installer",),
    )

    assert required_isolation(request) == IsolationClass.HARDWARE


def test_explicit_vm_boundary_overrides_trusted_workload() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.TRUSTED_BUILD,
        trust_level=TrustLevel.TRUSTED,
        command=("make",),
        requires_vm_boundary=True,
    )

    assert required_isolation(request) == IsolationClass.HARDWARE


def test_untrusted_full_system_request_uses_hardware_isolation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.SERVICE,
        trust_level=TrustLevel.UNTRUSTED,
        command=("systemctl", "start", "example"),
        requires_full_system=True,
    )

    assert required_isolation(request) == IsolationClass.HARDWARE


def test_trusted_full_system_request_can_use_host_os_isolation() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.SERVICE,
        trust_level=TrustLevel.TRUSTED,
        command=("systemctl", "status", "example"),
        requires_full_system=True,
    )

    assert required_isolation(request) == IsolationClass.HOST_OS


def test_kubernetes_runtime_requires_hardware_boundary() -> None:
    request = SandboxRequest(
        workload_type=WorkloadType.CONTAINER_WORKLOAD,
        trust_level=TrustLevel.TRUSTED,
        command=("container-entrypoint",),
        requires_kubernetes_runtime=True,
    )

    assert required_isolation(request) == IsolationClass.HARDWARE
