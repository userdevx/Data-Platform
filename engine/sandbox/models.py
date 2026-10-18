from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence


class IsolationClass(str, Enum):
    HOST_OS = "host_os"
    KERNEL_EMULATION = "kernel_emulation"
    HARDWARE = "hardware"


class RuntimeKind(str, Enum):
    PODMAN = "podman"
    INCUS_CONTAINER = "incus_container"
    GVISOR = "gvisor"
    QEMU_KVM = "qemu_kvm"
    INCUS_VM = "incus_vm"
    FIRECRACKER = "firecracker"
    KATA = "kata"


class WorkloadType(str, Enum):
    TRUSTED_BUILD = "trusted_build"
    TEST = "test"
    DEPENDENCY_INSTALL = "dependency_install"
    SCRIPT = "script"
    USER_SCRIPT = "user_script"
    GENERATED_CODE = "generated_code"
    BINARY = "binary"
    INSTALLER = "installer"
    SERVICE = "service"
    SYSTEM = "system"
    CONTAINER_WORKLOAD = "container_workload"


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    LIMITED = "limited"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    cpu_count: float = 1.0
    memory_mb: int = 512
    timeout_seconds: int = 60
    pids: int = 128


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    workload_type: WorkloadType
    trust_level: TrustLevel
    command: Sequence[str]

    working_directory: Path | None = None

    network_enabled: bool = False
    writable_workspace: bool = False

    requires_full_system: bool = False
    requires_vm_boundary: bool = False
    requires_kubernetes_runtime: bool = False

    environment: Mapping[str, str] = field(default_factory=dict)
    limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True, slots=True)
class RuntimeCapability:
    runtime_kind: RuntimeKind
    isolation_class: IsolationClass
    available: bool
    executable: Path | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SandboxSelection:
    isolation_class: IsolationClass
    runtime_kind: RuntimeKind
    reason: str


@dataclass(frozen=True, slots=True)
class SandboxResult:
    runtime_kind: RuntimeKind
    isolation_class: IsolationClass

    command: tuple[str, ...]

    exit_code: int
    stdout: str
    stderr: str

    timed_out: bool
    duration_seconds: float
