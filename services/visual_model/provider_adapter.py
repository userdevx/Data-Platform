from __future__ import annotations

from typing import Protocol, runtime_checkable

from services.visual_model.provider_contracts import (
    ModelStatus,
    VisualModelDescriptor,
    VisualProviderRequest,
    VisualProviderResult,
)


@runtime_checkable
class VisualProviderAdapter(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    def discover_models(
        self,
    ) -> tuple[VisualModelDescriptor, ...]:
        ...

    def check_model_health(
        self,
        *,
        model_id: str,
    ) -> ModelStatus:
        ...

    def analyze(
        self,
        *,
        model_id: str,
        request: VisualProviderRequest,
    ) -> VisualProviderResult:
        ...
