from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from services.visual_model.request_models import (
    VisualModelRequest,
)
from services.visual_model.response_models import (
    VisualModelResponse,
)


@dataclass(frozen=True)
class VisualModelRuntimeHealth:
    available: bool
    provider: str
    model_id: str
    status: str
    details: tuple[str, ...] = ()


@runtime_checkable
class VisualModelRuntime(Protocol):
    def health_check(
        self,
    ) -> VisualModelRuntimeHealth:
        """Return runtime availability without performing inference."""

        ...

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        """Analyze one validated visual request."""

        ...
