from __future__ import annotations

from engine.communication.email.provider import (
    EmailProvider,
)
from engine.communication.email.providers.gmail import (
    GmailEmailProvider,
)


class EmailProviderRegistry:
    def __init__(
        self,
    ) -> None:
        self._providers: dict[
            str,
            EmailProvider,
        ] = {}

        self.register(
            GmailEmailProvider()
        )

    def register(
        self,
        provider: EmailProvider,
    ) -> None:
        provider_id = str(
            provider.provider_id
        ).strip()

        if not provider_id:
            raise ValueError(
                "Email provider_id is required."
            )

        if provider_id in self._providers:
            raise ValueError(
                "Email provider is already registered: "
                + provider_id
            )

        self._providers[
            provider_id
        ] = provider

    def get(
        self,
        provider_id: str,
    ) -> EmailProvider:
        provider_id = str(
            provider_id
        ).strip()

        try:
            return self._providers[
                provider_id
            ]
        except KeyError as error:
            raise KeyError(
                "Unknown email provider: "
                + provider_id
            ) from error

    def all(
        self,
    ) -> tuple[
        EmailProvider,
        ...,
    ]:
        return tuple(
            self._providers.values()
        )

    def names(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        return tuple(
            self._providers.keys()
        )
