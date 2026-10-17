from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_user_id() -> str:
    return f"user_{uuid4().hex}"


class AccountStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    PROVISIONING_FAILED = "provisioning_failed"
    BINDING_FAILED = "binding_failed"
    DISABLED = "disabled"


class AccountRole(str, Enum):
    USER = "user"
    DEVELOPER = "developer"
    ADMIN = "admin"


@dataclass(slots=True)
class UserAccount:
    user_id: str
    username: str
    email: str
    role: AccountRole = AccountRole.USER
    status: AccountStatus = AccountStatus.PENDING
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        *,
        username: str,
        email: str,
        role: AccountRole = AccountRole.USER,
        status: AccountStatus = AccountStatus.PENDING,
    ) -> "UserAccount":
        clean_username = username.strip()
        clean_email = email.strip()

        if not clean_username:
            raise ValueError("username is required")

        if not clean_email:
            raise ValueError("email is required")

        return cls(
            user_id=new_user_id(),
            username=clean_username,
            email=clean_email,
            role=role,
            status=status,
        )

    def to_engine_value(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_engine_value(
        cls,
        value: dict[str, Any],
    ) -> "UserAccount":
        return cls(
            user_id=str(value["user_id"]),
            username=str(value["username"]),
            email=str(value["email"]),
            role=AccountRole(
                value.get(
                    "role",
                    AccountRole.USER.value,
                )
            ),
            status=AccountStatus(
                value.get(
                    "status",
                    AccountStatus.ACTIVE.value,
                )
            ),
            created_at=str(
                value.get(
                    "created_at",
                    utc_now_iso(),
                )
            ),
            updated_at=str(
                value.get(
                    "updated_at",
                    utc_now_iso(),
                )
            ),
        )


@dataclass(slots=True)
class MatrixIdentity:
    user_id: str
    matrix_user_id: str
    status: str = "active"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_engine_value(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "matrix_user_id": self.matrix_user_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_engine_value(
        cls,
        value: dict[str, Any],
    ) -> "MatrixIdentity":
        return cls(
            user_id=str(value["user_id"]),
            matrix_user_id=str(value["matrix_user_id"]),
            status=str(
                value.get("status", "active")
            ),
            created_at=str(
                value.get(
                    "created_at",
                    utc_now_iso(),
                )
            ),
            updated_at=str(
                value.get(
                    "updated_at",
                    utc_now_iso(),
                )
            ),
        )
