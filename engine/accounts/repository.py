from __future__ import annotations

from engine.accounts.models import (
    MatrixIdentity,
    UserAccount,
)
from engine.backend import get_backend
from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.query import QueryService


ACCOUNT_SOURCE_CATEGORY = "account"
ACCOUNT_PROFILE_TYPE = "user_profile"

COMMUNICATION_CATEGORY = "communication"
MATRIX_IDENTITY_TYPE = "matrix_identity"


class AccountRepository:
    def __init__(
        self,
        *,
        writer: DataEngineRecordWriter | None = None,
        query_service: QueryService | None = None,
    ) -> None:
        self._query_service = (
            query_service
            or QueryService(get_backend())
        )

        self._writer = (
            writer
            or DataEngineRecordWriter(
                query_service=self._query_service
            )
        )

    def save_account(
        self,
        account: UserAccount,
    ) -> UserAccount:
        self._writer.write(
            source=account.user_id,
            category=ACCOUNT_SOURCE_CATEGORY,
            data_type=ACCOUNT_PROFILE_TYPE,
            value=account.to_engine_value(),
            unit="record",
        )

        return account

    def create_account(
        self,
        account: UserAccount,
    ) -> UserAccount:
        return self.save_account(account)

    def list_accounts(
        self,
    ) -> list[UserAccount]:
        latest: dict[str, UserAccount] = {}

        for record in (
            self._query_service.get_all_records()
        ):
            if not isinstance(record, dict):
                continue

            if (
                record.get("category")
                != ACCOUNT_SOURCE_CATEGORY
            ):
                continue

            if (
                record.get("data_type")
                != ACCOUNT_PROFILE_TYPE
            ):
                continue

            value = record.get("value")

            if not isinstance(value, dict):
                continue

            try:
                account = (
                    UserAccount.from_engine_value(
                        value
                    )
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            current = latest.get(
                account.user_id
            )

            if (
                current is None
                or account.updated_at
                >= current.updated_at
            ):
                latest[
                    account.user_id
                ] = account

        return list(latest.values())

    def get_account(
        self,
        user_id: str,
    ) -> UserAccount | None:
        for account in self.list_accounts():
            if account.user_id == user_id:
                return account

        return None

    def bind_matrix_identity(
        self,
        identity: MatrixIdentity,
    ) -> MatrixIdentity:
        self._writer.write(
            source=identity.user_id,
            category=COMMUNICATION_CATEGORY,
            data_type=MATRIX_IDENTITY_TYPE,
            value=identity.to_engine_value(),
            unit="record",
        )

        return identity

    def get_matrix_identity(
        self,
        user_id: str,
    ) -> MatrixIdentity | None:
        matches: list[MatrixIdentity] = []

        for record in (
            self._query_service.get_all_records()
        ):
            if not isinstance(record, dict):
                continue

            if record.get("source") != user_id:
                continue

            if (
                record.get("category")
                != COMMUNICATION_CATEGORY
            ):
                continue

            if (
                record.get("data_type")
                != MATRIX_IDENTITY_TYPE
            ):
                continue

            value = record.get("value")

            if not isinstance(value, dict):
                continue

            try:
                matches.append(
                    MatrixIdentity.from_engine_value(
                        value
                    )
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

        if not matches:
            return None

        matches.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        return matches[0]
