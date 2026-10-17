from __future__ import annotations

from typing import Protocol

from engine.communication.messaging.models import (
    MessagingAccountRequest,
    MessagingIdentity,
    MessagingProviderStatus,
)


class MessagingProvider(Protocol):
    provider_id: str

    def status(self) -> MessagingProviderStatus:
        ...

    def register_account(
        self,
        request: MessagingAccountRequest,
    ) -> MessagingIdentity:
        ...
