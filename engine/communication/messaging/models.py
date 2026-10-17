from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MessagingAccountState(str, Enum):
    UNPROVISIONED = "unprovisioned"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class MessagingAccountRequest:
    user_id: str
    username: str
    password: str

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id is required")

        if not self.username.strip():
            raise ValueError("username is required")

        if not self.password:
            raise ValueError("password is required")


@dataclass(frozen=True, slots=True)
class MessagingIdentity:
    provider_id: str
    user_id: str
    external_user_id: str
    state: MessagingAccountState = MessagingAccountState.ACTIVE

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "user_id": self.user_id,
            "external_user_id": self.external_user_id,
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class MessagingProviderStatus:
    provider_id: str
    available: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "available": self.available,
            "detail": self.detail,
        }
