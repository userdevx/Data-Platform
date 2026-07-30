from __future__ import annotations

from collections.abc import Callable

from engine.intelligence.vision.analyzer import VisualAnalyzer
from engine.intelligence.vision.providers.unavailable import (
    UnavailableVisualAnalyzer,
)


VisualAnalyzerFactory = Callable[[], VisualAnalyzer]


class VisualAnalyzerRegistry:
    def __init__(self) -> None:
        self._factories: dict[
            str,
            VisualAnalyzerFactory,
        ] = {}

    def register(
        self,
        *,
        provider_name: str,
        factory: VisualAnalyzerFactory,
    ) -> None:
        clean_name = provider_name.strip()

        if not clean_name:
            raise ValueError(
                "provider_name is required."
            )

        if clean_name in self._factories:
            raise ValueError(
                f"Provider is already registered: {clean_name}"
            )

        self._factories[clean_name] = factory

    def create(
        self,
        provider_name: str | None,
    ) -> VisualAnalyzer:
        clean_name = (
            provider_name or ""
        ).strip()

        if not clean_name:
            return UnavailableVisualAnalyzer()

        factory = self._factories.get(clean_name)

        if factory is None:
            return UnavailableVisualAnalyzer()

        return factory()

    def registered_names(self) -> tuple[str, ...]:
        return tuple(
            sorted(self._factories)
        )
