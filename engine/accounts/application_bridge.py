from __future__ import annotations

import argparse
import json
import sys

from engine.accounts import (
    AccountRole,
    AccountService,
    AccountStatus,
)


def emit(value: dict) -> None:
    print(
        json.dumps(
            value,
            separators=(",", ":"),
        )
    )


def account_dict(account) -> dict:
    return account.to_engine_value()


def main() -> int:
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "has-active-admin"
    )

    prepare = subparsers.add_parser(
        "prepare-account"
    )
    prepare.add_argument(
        "--username",
        required=True,
    )
    prepare.add_argument(
        "--email",
        required=True,
    )
    prepare.add_argument(
        "--role",
        choices=[
            role.value
            for role in AccountRole
        ],
        required=True,
    )

    status = subparsers.add_parser(
        "set-status"
    )
    status.add_argument(
        "--user-id",
        required=True,
    )
    status.add_argument(
        "--status",
        choices=[
            item.value
            for item in AccountStatus
        ],
        required=True,
    )

    bind = subparsers.add_parser(
        "bind-messaging-identity"
    )
    bind.add_argument(
        "--user-id",
        required=True,
    )
    bind.add_argument(
        "--messaging-user-id",
        required=True,
    )

    args = parser.parse_args()

    service = AccountService()

    try:
        if args.command == "has-active-admin":
            emit({
                "status": "ok",
                "has_active_admin":
                    service.has_active_admin(),
            })
            return 0

        if args.command == "prepare-account":
            account = service.prepare_account(
                username=args.username,
                email=args.email,
                role=AccountRole(args.role),
            )

            emit({
                "status": "ok",
                "account": account_dict(
                    account
                ),
            })
            return 0

        if args.command == "set-status":
            account = service.set_status(
                args.user_id,
                AccountStatus(
                    args.status
                ),
            )

            emit({
                "status": "ok",
                "account": account_dict(
                    account
                ),
            })
            return 0

        if (
            args.command
            == "bind-messaging-identity"
        ):
            identity = (
                service.bind_matrix_identity(
                    user_id=args.user_id,
                    matrix_user_id=(
                        args.messaging_user_id
                    ),
                )
            )

            emit({
                "status": "ok",
                "identity":
                    identity.to_engine_value(),
            })
            return 0

    except Exception as error:
        emit({
            "status": "error",
            "error": str(error),
            "error_type":
                type(error).__name__,
        })
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
