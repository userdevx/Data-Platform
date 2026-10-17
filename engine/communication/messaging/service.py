from __future__ import annotations

from typing import Any

from engine.communication.messaging.models import (
    MessagingAccountRequest,
    MessagingIdentity,
)
from engine.communication.messaging.registry import (
    MessagingProviderRegistry,
)


class MessagingService:
    def __init__(
        self,
        registry: MessagingProviderRegistry | None = None,
    ) -> None:
        self.registry = (
            registry
            or MessagingProviderRegistry()
        )

    def provider_status(
        self,
    ) -> dict[str, Any]:
        providers = [
            provider.status().as_dict()
            for provider in self.registry.all()
        ]

        return {
            "status": "ok",
            "registered_provider_count": len(
                providers
            ),
            "providers": providers,
        }

    def register_account(
        self,
        *,
        provider_id: str,
        user_id: str,
        username: str,
        password: str,
    ) -> MessagingIdentity:
        provider = self.registry.get(
            provider_id
        )

        request = MessagingAccountRequest(
            user_id=user_id,
            username=username,
            password=password,
        )

        return provider.register_account(
            request
        )
