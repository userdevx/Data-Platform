from __future__ import annotations

import base64
import imaplib
import json
import os
import smtplib
import ssl
import urllib.request
from pathlib import Path
from typing import Any

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


KEYRING_SERVICE = "data-platform.communication"
KEYRING_ENTRY = "google_mail_xoauth2_v1"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://mail.google.com/",
]

USERINFO_URL = (
    "https://openidconnect.googleapis.com/v1/userinfo"
)


class GoogleConnectionError(RuntimeError):
    pass


def _client_file() -> Path:
    configured = os.environ.get(
        "GOOGLE_OAUTH_CLIENT_FILE",
        "~/.config/data-platform/communication/"
        "google-oauth-client.json",
    )

    return Path(configured).expanduser()


def _load_credentials() -> Credentials | None:
    stored = keyring.get_password(
        KEYRING_SERVICE,
        KEYRING_ENTRY,
    )

    if not stored:
        return None

    try:
        data = json.loads(stored)

        credentials = (
            Credentials.from_authorized_user_info(
                data,
                SCOPES,
            )
        )

        if not credentials.has_scopes(
            SCOPES
        ):
            return None

        return credentials

    except Exception as error:
        raise GoogleConnectionError(
            "Stored OAuth authorization could not be loaded. "
            f"error_type={type(error).__name__}"
        ) from error


def _save_credentials(
    credentials: Credentials,
) -> None:
    try:
        keyring.set_password(
            KEYRING_SERVICE,
            KEYRING_ENTRY,
            credentials.to_json(),
        )

    except Exception as error:
        raise GoogleConnectionError(
            "OAuth authorization could not be stored. "
            f"error_type={type(error).__name__}"
        ) from error


def _authorize() -> tuple[Credentials, bool]:
    client_file = _client_file()

    if not client_file.is_file():
        raise GoogleConnectionError(
            "OAuth desktop client file is missing: "
            + str(client_file)
        )

    credentials = _load_credentials()

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):
        try:
            credentials.refresh(
                Request()
            )
            _save_credentials(
                credentials
            )
        except Exception:
            credentials = None

    if credentials and credentials.valid:
        return credentials, True

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file),
        SCOPES,
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        success_message=(
            "Data Platform is connected to Google. "
            "You can close this browser window."
        ),
        access_type="offline",
        prompt="consent",
    )

    if not credentials.valid:
        raise GoogleConnectionError(
            "Google authorization did not return "
            "valid credentials."
        )

    if not credentials.refresh_token:
        raise GoogleConnectionError(
            "Google authorization returned no "
            "refresh token."
        )

    _save_credentials(
        credentials
    )

    return credentials, False


def _account_email(
    access_token: str,
) -> str:
    request = urllib.request.Request(
        USERINFO_URL,
        headers={
            "Authorization": (
                "Bearer " + access_token
            ),
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            profile = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except Exception as error:
        raise GoogleConnectionError(
            "Authenticated Google account "
            "could not be identified. "
            f"error_type={type(error).__name__}"
        ) from error

    email = str(
        profile.get(
            "email",
            "",
        )
    ).strip()

    if not email:
        raise GoogleConnectionError(
            "Google returned no account email."
        )

    return email


def _xoauth2_bytes(
    email: str,
    access_token: str,
) -> bytes:
    return (
        f"user={email}\x01"
        f"auth=Bearer {access_token}\x01\x01"
    ).encode("utf-8")


def _verify_imap(
    email: str,
    access_token: str,
) -> dict[str, Any]:
    client = None

    try:
        client = imaplib.IMAP4_SSL(
            "imap.gmail.com",
            993,
            ssl_context=ssl.create_default_context(),
        )

        auth = _xoauth2_bytes(
            email,
            access_token,
        )

        client.authenticate(
            "XOAUTH2",
            lambda _: auth,
        )

        status, _ = client.select(
            "INBOX",
            readonly=True,
        )

        if status != "OK":
            raise GoogleConnectionError(
                "IMAP authentication succeeded but "
                "INBOX could not be opened."
            )

        search_status, data = client.search(
            None,
            "UNSEEN",
        )

        unread = 0

        if (
            search_status == "OK"
            and data
            and data[0]
        ):
            unread = len(
                data[0].split()
            )

        return {
            "imap_connection": True,
            "imap_xoauth2": True,
            "inbox_access": True,
            "unread_count": unread,
        }

    except imaplib.IMAP4.error as error:
        raise GoogleConnectionError(
            "Gmail IMAP XOAUTH2 authentication failed. "
            f"gmail_response={error!r}"
        ) from error

    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def _verify_smtp(
    email: str,
    access_token: str,
) -> dict[str, Any]:
    raw = _xoauth2_bytes(
        email,
        access_token,
    )

    encoded = base64.b64encode(
        raw
    ).decode("ascii")

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            context=ssl.create_default_context(),
            timeout=30,
        ) as client:

            code, response = client.docmd(
                "AUTH",
                "XOAUTH2 " + encoded,
            )

            if code != 235:
                raise GoogleConnectionError(
                    "Gmail SMTP XOAUTH2 authentication "
                    "was rejected. "
                    f"smtp_code={code} "
                    f"smtp_response={response!r}"
                )

        return {
            "smtp_connection": True,
            "smtp_xoauth2": True,
        }

    except GoogleConnectionError:
        raise

    except Exception as error:
        raise GoogleConnectionError(
            "Gmail SMTP XOAUTH2 connection failed. "
            f"error_type={type(error).__name__}"
        ) from error


def connect_and_verify() -> dict[str, Any]:
    credentials, restored = _authorize()

    if (
        not credentials.token
        or not credentials.valid
    ):
        raise GoogleConnectionError(
            "No valid OAuth access token is available."
        )

    email = _account_email(
        credentials.token
    )

    imap_result = _verify_imap(
        email,
        credentials.token,
    )

    smtp_result = _verify_smtp(
        email,
        credentials.token,
    )

    return {
        "status": "connected",
        "account": email,
        "oauth_authorization": True,
        "connection_restored": restored,
        "refresh_token_stored": bool(
            credentials.refresh_token
        ),
        **imap_result,
        **smtp_result,
    }
