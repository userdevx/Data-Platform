from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SERVICE = "data-platform.communication"

CREDENTIAL_KEYS = frozenset(
    {
        "email_address",
        "email_password",
    }
)


class CredentialStoreUnavailableError(RuntimeError):
    """The system keyring could not be reached."""


class CredentialNotFoundError(LookupError):
    """No credential is stored under this account and key."""


@dataclass(frozen=True)
class CredentialReference:
    service: str
    account: str
    key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "account": self.account,
            "key": self.key,
            "source": "keyring",
        }


def _backend():
    try:
        import keyring
    except ImportError as error:
        raise CredentialStoreUnavailableError(
            "The keyring package is not installed."
        ) from error

    return keyring


def _validate_key(key: str) -> str:
    clean = str(key or "").strip().lower()

    if clean not in CREDENTIAL_KEYS:
        raise ValueError(
            "Unknown credential key: "
            + repr(key)
            + ". Known keys: "
            + ", ".join(sorted(CREDENTIAL_KEYS))
        )

    return clean


def _validate_account(account: str) -> str:
    clean = str(account or "").strip()

    if not clean:
        raise ValueError(
            "An account identifier is required."
        )

    return clean


def _entry(account: str, key: str) -> str:
    return account + ":" + key


def set_credential(
    *,
    account: str,
    key: str,
    secret: str,
) -> CredentialReference:
    account = _validate_account(account)
    key = _validate_key(key)
    secret = str(secret or "")

    if not secret:
        raise ValueError(
            "Refusing to store an empty credential."
        )

    keyring = _backend()

    try:
        keyring.set_password(
            SERVICE,
            _entry(account, key),
            secret,
        )
    except Exception as error:
        raise CredentialStoreUnavailableError(
            "The system keyring rejected the credential write. "
            f"error_type={type(error).__name__}"
        ) from error

    return CredentialReference(
        service=SERVICE,
        account=account,
        key=key,
    )


def get_credential(
    *,
    account: str,
    key: str,
) -> str:
    account = _validate_account(account)
    key = _validate_key(key)

    keyring = _backend()

    try:
        secret = keyring.get_password(
            SERVICE,
            _entry(account, key),
        )
    except Exception as error:
        raise CredentialStoreUnavailableError(
            "The system keyring could not read the credential. "
            f"error_type={type(error).__name__}"
        ) from error

    if secret is None:
        raise CredentialNotFoundError(
            "No credential stored for account "
            + repr(account)
            + " under key "
            + repr(key)
        )

    return secret


def delete_credential(
    *,
    account: str,
    key: str,
) -> bool:
    account = _validate_account(account)
    key = _validate_key(key)

    keyring = _backend()

    try:
        keyring.delete_password(
            SERVICE,
            _entry(account, key),
        )
    except keyring.errors.PasswordDeleteError:
        return False
    except Exception as error:
        raise CredentialStoreUnavailableError(
            "The system keyring could not delete the credential. "
            f"error_type={type(error).__name__}"
        ) from error

    return True


def stored_keys(
    *,
    account: str,
) -> tuple[str, ...]:
    account = _validate_account(account)
    present: list[str] = []

    for key in sorted(CREDENTIAL_KEYS):
        try:
            get_credential(
                account=account,
                key=key,
            )
        except CredentialNotFoundError:
            continue

        present.append(key)

    return tuple(present)


def credential_status(
    *,
    account: str,
) -> dict[str, Any]:
    account = _validate_account(account)

    try:
        present = stored_keys(
            account=account,
        )
        available = True
        detail = ""
    except CredentialStoreUnavailableError as error:
        present = ()
        available = False
        detail = str(error)

    return {
        "service": SERVICE,
        "account": account,
        "source": "keyring",
        "keyring_available": available,
        "stored_keys": list(present),
        "missing_keys": sorted(
            CREDENTIAL_KEYS - set(present)
        ),
        "detail": detail,
    }
