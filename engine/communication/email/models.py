from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmailMessage:
    provider_id: str
    account: str
    message_id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    date: str
    unread: bool
    body_fetched: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "account": self.account,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "from": self.sender,
            "to": self.recipient,
            "subject": self.subject,
            "date": self.date,
            "unread": self.unread,
            "body_fetched": self.body_fetched,
        }


@dataclass(frozen=True)
class EmailProviderResult:
    provider_id: str
    connected: bool
    account: str | None
    messages_listed: bool
    unread_count: int | None
    returned_count: int | None
    messages: list[dict[str, Any]] = field(
        default_factory=list
    )
    error_type: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "connected": self.connected,
            "account": self.account,
            "messages_listed": self.messages_listed,
            "unread_count": self.unread_count,
            "returned_count": self.returned_count,
            "messages": self.messages,
            "error_type": self.error_type,
            "error": self.error,
        }
