from __future__ import annotations

from engine.communication.messaging.provider import (
    MessagingProvider,
)


class MessagingProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MessagingProvider] = {}

    def register(
        self,
        provider: MessagingProvider,
    ) -> None:
        provider_id = str(provider.provider_id).strip()

        if not provider_id:
            raise ValueError(
                "Messaging provider_id is required."
            )

        if provider_id in self._providers:
            raise ValueError(
                "Messaging provider is already registered: "
                + provider_id
            )

        self._providers[provider_id] = provider

    def get(
        self,
        provider_id: str,
    ) -> MessagingProvider:
        provider_id = str(provider_id).strip()

        try:
            return self._providers[provider_id]
        except KeyError as error:
            raise KeyError(
                "Unknown messaging provider: "
                + provider_id
            ) from error

    def all(
        self,
    ) -> tuple[MessagingProvider, ...]:
        return tuple(
            self._providers.values()
        )

    def names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._providers.keys()
        )
