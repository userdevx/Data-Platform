from __future__ import annotations

from typing import Protocol

from engine.communication.email.models import (
    EmailProviderResult,
)


class EmailProvider(Protocol):
    provider_id: str

    def connection_available(
        self,
    ) -> bool:
        ...

    def read_unread(
        self,
    ) -> EmailProviderResult:
        ...

    def read_recent(
        self,
        *,
        limit: int = 1,
    ) -> EmailProviderResult:
        ...
