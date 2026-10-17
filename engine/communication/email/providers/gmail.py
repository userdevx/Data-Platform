from __future__ import annotations

from typing import Any

from engine.communication.email.models import (
    EmailProviderResult,
)
from engine.communication.email.providers.gmail_read import (
    read_recent_email,
    read_unread_email,
)
from engine.communication.gmail_api_connection import (
    restore_connection,
)


class GmailEmailProvider:
    provider_id = "gmail"

    def connection_available(
        self,
    ) -> bool:
        try:
            connection = restore_connection()

            return bool(
                connection.get(
                    "connection_restored"
                )
                and connection.get(
                    "gmail_api_access"
                )
                and not connection.get(
                    "browser_authorization"
                )
            )
        except Exception:
            return False

    @staticmethod
    def _connected_account() -> str:
        connection = restore_connection()

        account = str(
            connection.get(
                "account",
                "",
            )
        ).strip()

        if not account:
            raise RuntimeError(
                "Connected email account is unavailable."
            )

        return account

    def _normalize(
        self,
        *,
        account: str,
        result: dict[str, Any],
    ) -> EmailProviderResult:
        raw_messages = result.get(
            "messages",
            [],
        )

        if not isinstance(
            raw_messages,
            list,
        ):
            raw_messages = []

        messages: list[
            dict[str, Any]
        ] = []

        for message in raw_messages:
            if not isinstance(
                message,
                dict,
            ):
                continue

            normalized = dict(
                message
            )

            normalized[
                "provider_id"
            ] = self.provider_id

            normalized[
                "account"
            ] = account

            messages.append(
                normalized
            )

        unread_value = result.get(
            "unread_count"
        )

        unread_count = (
            int(unread_value)
            if unread_value is not None
            else None
        )

        return EmailProviderResult(
            provider_id=self.provider_id,
            connected=True,
            account=account,
            messages_listed=bool(
                result.get(
                    "messages_listed",
                    False,
                )
            ),
            unread_count=unread_count,
            returned_count=len(
                messages
            ),
            messages=messages,
        )

    def _failure(
        self,
        error: Exception,
    ) -> EmailProviderResult:
        return EmailProviderResult(
            provider_id=self.provider_id,
            connected=False,
            account=None,
            messages_listed=False,
            unread_count=None,
            returned_count=None,
            messages=[],
            error_type=type(
                error
            ).__name__,
            error=str(
                error
            ),
        )

    def read_unread(
        self,
    ) -> EmailProviderResult:
        try:
            account = (
                self._connected_account()
            )

            result = read_unread_email(
                account=account
            )

            return self._normalize(
                account=account,
                result=result,
            )

        except Exception as error:
            return self._failure(
                error
            )

    def read_recent(
        self,
        *,
        limit: int = 1,
    ) -> EmailProviderResult:
        try:
            account = (
                self._connected_account()
            )

            result = read_recent_email(
                account=account,
                limit=limit,
            )

            return self._normalize(
                account=account,
                result=result,
            )

        except Exception as error:
            return self._failure(
                error
            )
