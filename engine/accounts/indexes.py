from __future__ import annotations

from dataclasses import dataclass, field

from engine.accounts.models import UserAccount


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def normalize_email(value: str) -> str:
    return value.strip().casefold()


@dataclass(slots=True)
class AccountIndexes:
    users_by_id: dict[str, UserAccount] = field(
        default_factory=dict
    )
    user_id_by_username: dict[str, str] = field(
        default_factory=dict
    )
    user_id_by_email: dict[str, str] = field(
        default_factory=dict
    )

    def clear(self) -> None:
        self.users_by_id.clear()
        self.user_id_by_username.clear()
        self.user_id_by_email.clear()

    def add(self, account: UserAccount) -> None:
        username_key = normalize_username(
            account.username
        )
        email_key = normalize_email(
            account.email
        )

        existing_username = (
            self.user_id_by_username.get(
                username_key
            )
        )

        if (
            existing_username is not None
            and existing_username
            != account.user_id
        ):
            raise ValueError(
                "username already exists"
            )

        existing_email = (
            self.user_id_by_email.get(
                email_key
            )
        )

        if (
            existing_email is not None
            and existing_email
            != account.user_id
        ):
            raise ValueError(
                "email already exists"
            )

        self.users_by_id[
            account.user_id
        ] = account

        self.user_id_by_username[
            username_key
        ] = account.user_id

        self.user_id_by_email[
            email_key
        ] = account.user_id

    def rebuild(
        self,
        accounts: list[UserAccount],
    ) -> None:
        self.clear()

        for account in accounts:
            self.add(account)

    def get(
        self,
        user_id: str,
    ) -> UserAccount | None:
        return self.users_by_id.get(user_id)

    def resolve_username(
        self,
        username: str,
    ) -> str | None:
        return self.user_id_by_username.get(
            normalize_username(username)
        )

    def resolve_email(
        self,
        email: str,
    ) -> str | None:
        return self.user_id_by_email.get(
            normalize_email(email)
        )
