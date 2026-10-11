from __future__ import annotations

from abc import ABC, abstractmethod

from engine.sandbox.models import SandboxRequest, SandboxResult


class SandboxRuntime(ABC):
    @abstractmethod
    def execute(self, request: SandboxRequest) -> SandboxResult:
        raise NotImplementedError
