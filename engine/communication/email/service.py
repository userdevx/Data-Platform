from __future__ import annotations

from typing import Any

from engine.communication.email.registry import (
    EmailProviderRegistry,
)


class EmailService:
    def __init__(
        self,
        registry: EmailProviderRegistry | None = None,
    ) -> None:
        self.registry = (
            registry
            or EmailProviderRegistry()
        )

    def _providers(
        self,
        provider_id: str | None,
    ):
        if provider_id:
            return (
                self.registry.get(
                    provider_id
                ),
            )

        return self.registry.all()

    def read_unread(
        self,
        *,
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        providers = self._providers(
            provider_id
        )

        results = []

        connected_provider_count = 0
        checked_provider_count = 0
        failed_provider_count = 0

        total_unread: int | None = None
        total_returned: int | None = None

        for provider in providers:
            if not provider.connection_available():
                continue

            connected_provider_count += 1
            checked_provider_count += 1

            result = provider.read_unread()

            results.append(
                result.as_dict()
            )

            if result.connected:
                if (
                    result.unread_count
                    is not None
                ):
                    total_unread = (
                        (total_unread or 0)
                        + result.unread_count
                    )

                if (
                    result.returned_count
                    is not None
                ):
                    total_returned = (
                        (total_returned or 0)
                        + result.returned_count
                    )
            else:
                failed_provider_count += 1

        status = (
            "error"
            if (
                checked_provider_count > 0
                and total_unread is None
            )
            else "ok"
        )

        return {
            "status": status,
            "operation": "unread",
            "provider_filter": provider_id,
            "registered_provider_count": len(
                self.registry.names()
            ),
            "connected_provider_count": (
                connected_provider_count
            ),
            "checked_provider_count": (
                checked_provider_count
            ),
            "failed_provider_count": (
                failed_provider_count
            ),
            "total_unread": total_unread,
            "total_returned": total_returned,
            "providers": results,
        }

    def read_recent(
        self,
        *,
        provider_id: str | None = None,
        limit: int = 1,
    ) -> dict[str, Any]:
        try:
            requested_limit = int(
                limit
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "limit must be an integer."
            ) from error

        requested_limit = max(
            1,
            min(
                20,
                requested_limit,
            ),
        )

        providers = self._providers(
            provider_id
        )

        results = []

        connected_provider_count = 0
        checked_provider_count = 0
        successful_provider_count = 0
        failed_provider_count = 0
        total_returned = 0

        for provider in providers:
            if not provider.connection_available():
                continue

            connected_provider_count += 1
            checked_provider_count += 1

            result = provider.read_recent(
                limit=requested_limit
            )

            results.append(
                result.as_dict()
            )

            if result.connected:
                successful_provider_count += 1

                total_returned += (
                    result.returned_count
                    or 0
                )
            else:
                failed_provider_count += 1

        if connected_provider_count == 0:
            status = "unavailable"
        elif successful_provider_count == 0:
            status = "error"
        else:
            status = "ok"

        return {
            "status": status,
            "operation": "recent",
            "provider_filter": provider_id,
            "registered_provider_count": len(
                self.registry.names()
            ),
            "connected_provider_count": (
                connected_provider_count
            ),
            "checked_provider_count": (
                checked_provider_count
            ),
            "successful_provider_count": (
                successful_provider_count
            ),
            "failed_provider_count": (
                failed_provider_count
            ),
            "total_returned": (
                total_returned
            ),
            "providers": results,
        }
