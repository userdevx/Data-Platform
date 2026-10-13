from __future__ import annotations

from collections.abc import Callable

from engine.sandbox.models import (
    RuntimeKind,
    SandboxRequest,
    SandboxResult,
)
from engine.sandbox.runtime.base import SandboxRuntime
from engine.sandbox.runtime.gvisor import GVisorRuntime
from engine.sandbox.runtime.incus_container import (
    IncusContainerRuntime,
)
from engine.sandbox.runtime.incus_vm import (
    IncusVmRuntime,
)
from engine.sandbox.runtime.podman import PodmanRuntime
from engine.sandbox.selector import select_runtime


RuntimeFactory = Callable[[], SandboxRuntime]


class SandboxManager:
    def __init__(
        self,
        runtime_factories: dict[
            RuntimeKind,
            RuntimeFactory,
        ]
        | None = None,
    ) -> None:
        self._runtime_factories = (
            runtime_factories
            if runtime_factories is not None
            else {
                RuntimeKind.PODMAN: PodmanRuntime,
                RuntimeKind.INCUS_CONTAINER: IncusContainerRuntime,
                RuntimeKind.GVISOR: GVisorRuntime,
                RuntimeKind.INCUS_VM: IncusVmRuntime,
            }
        )

    def execute(
        self,
        request: SandboxRequest,
    ) -> SandboxResult:
        selection = select_runtime(request)

        factory = self._runtime_factories.get(
            selection.runtime_kind
        )

        if factory is None:
            raise RuntimeError(
                f"No runtime factory registered for "
                f"{selection.runtime_kind.value}"
            )

        runtime = factory()

        return runtime.execute(request)
