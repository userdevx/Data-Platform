from __future__ import annotations

from typing import Any

from engine.communication.email.service import (
    EmailService,
)


class EmailReadTool:
    """
    Read normalized email metadata through EmailService.

    Provider-specific behavior remains behind provider adapters.
    Message bodies are not retrieved by this tool.
    """

    name = "email_read"

    def __init__(
        self,
        service: EmailService | None = None,
    ) -> None:
        self._service = service

    @staticmethod
    def _message_limit(
        arguments: dict[str, Any],
        *,
        default: int,
    ) -> int:
        try:
            value = int(
                arguments.get(
                    "max_messages",
                    default,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            value = default

        return max(
            1,
            min(
                20,
                value,
            ),
        )

    @staticmethod
    def _collect_messages(
        result: dict[str, Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        messages: list[
            dict[str, Any]
        ] = []

        providers = result.get(
            "providers",
            [],
        )

        if not isinstance(
            providers,
            list,
        ):
            return messages

        for provider in providers:
            if not isinstance(
                provider,
                dict,
            ):
                continue

            if not provider.get(
                "connected"
            ):
                continue

            provider_messages = provider.get(
                "messages",
                [],
            )

            if not isinstance(
                provider_messages,
                list,
            ):
                continue

            for message in provider_messages:
                if not isinstance(
                    message,
                    dict,
                ):
                    continue

                if len(messages) >= limit:
                    return messages

                messages.append(
                    {
                        "provider_id": (
                            message.get(
                                "provider_id"
                            )
                        ),
                        "account": (
                            message.get(
                                "account"
                            )
                        ),
                        "id": (
                            message.get(
                                "id",
                                "",
                            )
                        ),
                        "thread_id": (
                            message.get(
                                "thread_id",
                                "",
                            )
                        ),
                        "message_id": (
                            message.get(
                                "message_id",
                                "",
                            )
                        ),
                        "from": (
                            message.get(
                                "from",
                                "",
                            )
                        ),
                        "to": (
                            message.get(
                                "to",
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
                        "unread": bool(
                            message.get(
                                "unread",
                                False,
                            )
                        ),
                    }
                )

        return messages

    @staticmethod
    def _failed_providers(
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        failures: list[
            dict[str, Any]
        ] = []

        providers = result.get(
            "providers",
            [],
        )

        if not isinstance(
            providers,
            list,
        ):
            return failures

        for provider in providers:
            if not isinstance(
                provider,
                dict,
            ):
                continue

            if provider.get(
                "connected"
            ):
                continue

            failures.append(
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
            )

        return failures

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

        operation = str(
            arguments.get(
                "operation",
                "unread",
            )
        ).strip().casefold()

        provider_id = str(
            arguments.get(
                "provider_id",
                "",
            )
        ).strip()

        if operation not in {
            "unread",
            "latest_received",
        }:
            return {
                "success": False,
                "operation": operation,
                "error": (
                    "unsupported_email_operation"
                ),
                "body_fetched": False,
            }

        default_limit = (
            1
            if operation == "latest_received"
            else 5
        )

        max_messages = self._message_limit(
            arguments,
            default=default_limit,
        )

        if operation == "latest_received":
            result = service.read_recent(
                provider_id=(
                    provider_id
                    or None
                ),
                limit=max_messages,
            )
        else:
            result = service.read_unread(
                provider_id=(
                    provider_id
                    or None
                )
            )

        connected_provider_count = int(
            result.get(
                "connected_provider_count",
                0,
            )
            or 0
        )

        if connected_provider_count == 0:
            return {
                "success": False,
                "operation": operation,
                "error": (
                    "email_provider_unavailable"
                ),
                "unread_count": None,
                "returned_count": None,
                "connected_provider_count": 0,
                "body_fetched": False,
                "failed_providers": (
                    self._failed_providers(
                        result
                    )
                ),
            }

        if result.get("status") != "ok":
            return {
                "success": False,
                "operation": operation,
                "error": (
                    "email_read_failed"
                ),
                "unread_count": None,
                "returned_count": None,
                "connected_provider_count": (
                    connected_provider_count
                ),
                "body_fetched": False,
                "failed_providers": (
                    self._failed_providers(
                        result
                    )
                ),
            }

        messages = self._collect_messages(
            result,
            limit=max_messages,
        )

        return {
            "success": True,
            "operation": operation,
            "unread_count": (
                result.get(
                    "total_unread"
                )
                if operation == "unread"
                else None
            ),
            "returned_count": len(
                messages
            ),
            "connected_provider_count": (
                connected_provider_count
            ),
            "failed_provider_count": (
                result.get(
                    "failed_provider_count",
                    0,
                )
            ),
            "body_fetched": False,
            "messages": messages,
        }
