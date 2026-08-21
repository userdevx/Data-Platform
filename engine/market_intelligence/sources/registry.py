from __future__ import annotations

from engine.market_intelligence.sources.base import PublicSource


class PublicSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, PublicSource] = {}

    def register(
        self,
        source: PublicSource,
    ) -> None:
        key = self._normalize_name(
            source.source_name
        )

        self._sources[key] = source

    def unregister(
        self,
        source_name: str,
    ) -> None:
        key = self._normalize_name(
            source_name
        )

        self._sources.pop(
            key,
            None,
        )

    def get(
        self,
        source_name: str,
    ) -> PublicSource:
        key = self._normalize_name(
            source_name
        )

        try:
            return self._sources[key]
        except KeyError as exc:
            raise KeyError(
                "Source is not registered: "
                f"{source_name}"
            ) from exc

    def has(
        self,
        source_name: str,
    ) -> bool:
        key = self._normalize_name(
            source_name
        )

        return key in self._sources

    def all(
        self,
    ) -> tuple[PublicSource, ...]:
        return tuple(
            self._sources[key]
            for key in sorted(
                self._sources
            )
        )

    def available_sources(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                self._sources
            )
        )

    @staticmethod
    def _normalize_name(
        source_name: str,
    ) -> str:
        normalized = (
            source_name
            .strip()
            .casefold()
        )

        if not normalized:
            raise ValueError(
                "Source name cannot be empty."
            )

        return normalized
