from __future__ import annotations

from typing import Any

from engine.communication.email.service import (
    EmailService,
)


class EmailReadTool:
    """
    Unread email as a tool the model can call.

    Wraps the existing EmailService rather than reaching a provider
    directly, so account resolution, provider selection and the
    metadata-only boundary stay in one place.
    """

    name = "email_read"

    def __init__(
        self,
        service: EmailService | None = None,
    ) -> None:
        self._service = service

    def execute(
        self,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del context

        service = (
            self._service
            or EmailService()
        )

        provider_id = str(
            arguments.get(
                "provider_id",
                "",
            )
        ).strip()

        result = service.read_unread(
            provider_id=(
                provider_id
                or None
            )
        )

        # A read that failed has no count. Reporting zero here would
        # make "could not be read" indistinguishable from "the inbox
        # is empty".
        if (
            result.get("status")
            != "ok"
        ):
            failures = [
                {
                    "provider_id": (
                        provider.get(
                            "provider_id"
                        )
                    ),
                    "error_type": (
                        provider.get(
                            "error_type"
                        )
                    ),
                }
                for provider in result.get(
                    "providers",
                    [],
                )
                if not provider.get(
                    "connected"
                )
            ]

            return {
                "success": False,
                "error": (
                    "email_read_failed"
                ),
                "unread_count": None,
                "failed_providers": (
                    failures
                ),
            }

        try:
            max_messages = int(
                arguments.get(
                    "max_messages",
                    5,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            max_messages = 5

        max_messages = max(
            1,
            min(
                20,
                max_messages,
            ),
        )

        messages: list[
            dict[str, Any]
        ] = []

        for provider in result.get(
            "providers",
            [],
        ):
            if not provider.get(
                "connected"
            ):
                continue

            for message in provider.get(
                "messages",
                [],
            ):
                if (
                    len(messages)
                    >= max_messages
                ):
                    break

                messages.append(
                    {
                        "provider_id": (
                            message.get(
                                "provider_id"
                            )
                        ),
                        "from": (
                            message.get(
                                "from",
                                "",
                            )
                        ),
                        "subject": (
                            message.get(
                                "subject",
                                "",
                            )
                        ),
                        "date": (
                            message.get(
                                "date",
                                "",
                            )
                        ),
                    }
                )

        return {
            "success": True,
            "unread_count": (
                result.get(
                    "total_unread"
                )
            ),
            "returned_count": len(
                messages
            ),
            "connected_provider_count": (
                result.get(
                    "connected_provider_count"
                )
            ),
            "failed_provider_count": (
                result.get(
                    "failed_provider_count"
                )
            ),
            "body_fetched": False,
            "messages": messages,
        }
