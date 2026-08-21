from __future__ import annotations

from abc import ABC, abstractmethod

from engine.market_intelligence.models import (
    PublicContentRecord,
)


class PublicSource(ABC):
    @property
    @abstractmethod
    def source_name(
        self,
    ) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def source_type(
        self,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[PublicContentRecord]:
        raise NotImplementedError
