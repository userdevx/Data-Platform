from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from engine.sandbox.manager import SandboxManager
from engine.sandbox.models import RuntimeKind
from engine.sandbox.runtime.firecracker import FirecrackerRuntime
from engine.sandbox.runtime.gvisor import GVisorRuntime
from engine.sandbox.runtime.incus_container import IncusContainerRuntime
from engine.sandbox.runtime.incus_vm import IncusVmRuntime
from engine.sandbox.runtime.podman import PodmanRuntime


@dataclass(frozen=True)
class BuilderExecutionPolicy:
    image_id: str
    cpu_count: float
    memory_mb: int
    pids: int

    @classmethod
    def load(cls, project_root: Path) -> "BuilderExecutionPolicy":
        path = (
            Path(project_root)
            / "config/application_engineering/active.json"
        )
        raw = json.loads(path.read_text(encoding="utf-8"))

        if (
            raw.get("definition_version") != 1
            or raw.get("configuration_status") != "active"
        ):
            raise ValueError("Invalid Builder configuration")

        image = raw.get("builder_image_id")

        if (
            not isinstance(image, str)
            or len(image) != 71
            or not image.startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in image[7:])
        ):
            raise ValueError("Invalid immutable Builder image ID")

        cpu = raw.get("cpu_count")
        memory = raw.get("memory_mb")
        pids = raw.get("pids")

        if type(cpu) not in (int, float) or not 0 < cpu <= 2:
            raise ValueError("Invalid CPU limit")
        if type(memory) is not int or not 128 <= memory <= 2048:
            raise ValueError("Invalid memory limit")
        if type(pids) is not int or not 16 <= pids <= 256:
            raise ValueError("Invalid process limit")

        return cls(image, float(cpu), memory, pids)


def make_builder_manager(image_id: str) -> SandboxManager:
    return SandboxManager({
        RuntimeKind.PODMAN: PodmanRuntime,
        RuntimeKind.INCUS_CONTAINER: IncusContainerRuntime,
        RuntimeKind.GVISOR: lambda: GVisorRuntime(image=image_id),
        RuntimeKind.INCUS_VM: IncusVmRuntime,
        RuntimeKind.FIRECRACKER: FirecrackerRuntime,
    })
