from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)


@dataclass(frozen=True)
class VisualRuntimeHealth:
    available: bool
    provider: str
    model_id: str
    message: str
    details: tuple[str, ...] = ()


@runtime_checkable
class VisualModelRuntime(Protocol):
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        """Return runtime availability without inference."""
        ...

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        """Analyze one validated visual request."""
        ...
