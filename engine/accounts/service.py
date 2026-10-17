from __future__ import annotations

from dataclasses import replace

from engine.accounts.indexes import (
    AccountIndexes,
)
from engine.accounts.models import (
    AccountRole,
    AccountStatus,
    MatrixIdentity,
    UserAccount,
    utc_now_iso,
)
from engine.accounts.repository import (
    AccountRepository,
)


_RETRYABLE = {
    AccountStatus.PENDING,
    AccountStatus.PROVISIONING,
    AccountStatus.PROVISIONING_FAILED,
    AccountStatus.BINDING_FAILED,
}


class AccountService:
    def __init__(
        self,
        repository: AccountRepository | None = None,
        indexes: AccountIndexes | None = None,
    ) -> None:
        self._repository = (
            repository
            or AccountRepository()
        )

        self._indexes = (
            indexes
            or AccountIndexes()
        )

        self.rebuild_indexes()

    def rebuild_indexes(self) -> None:
        self._indexes.rebuild(
            self._repository.list_accounts()
        )

    def create_account(
        self,
        *,
        username: str,
        email: str,
        role: AccountRole = AccountRole.USER,
        status: AccountStatus = AccountStatus.PENDING,
    ) -> UserAccount:
        if (
            self._indexes.resolve_username(
                username
            )
            is not None
        ):
            raise ValueError(
                "username already exists"
            )

        if (
            self._indexes.resolve_email(
                email
            )
            is not None
        ):
            raise ValueError(
                "email already exists"
            )

        account = UserAccount.create(
            username=username,
            email=email,
            role=role,
            status=status,
        )

        self._repository.create_account(
            account
        )

        self._indexes.add(account)

        return account

    def prepare_account(
        self,
        *,
        username: str,
        email: str,
        role: AccountRole,
    ) -> UserAccount:
        username_account = (
            self.resolve_username(username)
        )
        email_account = (
            self.resolve_email(email)
        )

        if (
            username_account is None
            and email_account is None
        ):
            return self.create_account(
                username=username,
                email=email,
                role=role,
                status=AccountStatus.PENDING,
            )

        if (
            username_account is None
            or email_account is None
            or username_account.user_id
            != email_account.user_id
        ):
            raise ValueError(
                "username or email belongs to another account"
            )

        account = username_account

        if account.role != role:
            raise ValueError(
                "existing account role does not match"
            )

        if account.status not in _RETRYABLE:
            raise ValueError(
                "account already exists"
            )

        return self.set_status(
            account.user_id,
            AccountStatus.PENDING,
        )

    def set_status(
        self,
        user_id: str,
        status: AccountStatus,
    ) -> UserAccount:
        account = self.get_account(user_id)

        if account is None:
            raise ValueError(
                "DataWorc account does not exist"
            )

        updated = replace(
            account,
            status=status,
            updated_at=utc_now_iso(),
        )

        self._repository.save_account(
            updated
        )

        self.rebuild_indexes()

        return updated

    def has_active_admin(self) -> bool:
        return any(
            account.role == AccountRole.ADMIN
            and account.status
            == AccountStatus.ACTIVE
            for account
            in self._repository.list_accounts()
        )

    def get_account(
        self,
        user_id: str,
    ) -> UserAccount | None:
        return self._indexes.get(user_id)

    def resolve_username(
        self,
        username: str,
    ) -> UserAccount | None:
        user_id = (
            self._indexes.resolve_username(
                username
            )
        )

        if user_id is None:
            return None

        return self._indexes.get(user_id)

    def resolve_email(
        self,
        email: str,
    ) -> UserAccount | None:
        user_id = (
            self._indexes.resolve_email(
                email
            )
        )

        if user_id is None:
            return None

        return self._indexes.get(user_id)

    def bind_matrix_identity(
        self,
        *,
        user_id: str,
        matrix_user_id: str,
    ) -> MatrixIdentity:
        account = self.get_account(user_id)

        if account is None:
            raise ValueError(
                "DataWorc account does not exist"
            )

        existing = (
            self._repository
            .get_matrix_identity(user_id)
        )

        if existing is not None:
            if (
                existing.matrix_user_id
                == matrix_user_id
            ):
                return existing

            raise ValueError(
                "user already has a Matrix identity"
            )

        identity = MatrixIdentity(
            user_id=user_id,
            matrix_user_id=(
                matrix_user_id.strip()
            ),
        )

        if not identity.matrix_user_id:
            raise ValueError(
                "matrix_user_id is required"
            )

        return (
            self._repository
            .bind_matrix_identity(identity)
        )

    def get_matrix_identity(
        self,
        user_id: str,
    ) -> MatrixIdentity | None:
        return (
            self._repository
            .get_matrix_identity(user_id)
        )
