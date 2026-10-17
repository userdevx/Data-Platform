from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import keyring

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


CLIENT_FILE = Path(
    "~/.config/data-platform/communication/"
    "google-oauth-client.json"
).expanduser()

KEYRING_SERVICE = "data-platform.communication"
KEYRING_KEY = "gmail_api_readonly_refresh_token_v1"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

PROFILE_URL = (
    "https://gmail.googleapis.com/"
    "gmail/v1/users/me/profile"
)


class GmailConnectionError(RuntimeError):
    pass


def _client_configuration() -> dict[str, str]:
    if not CLIENT_FILE.is_file():
        raise GmailConnectionError(
            f"OAuth client file missing: {CLIENT_FILE}"
        )

    data = json.loads(
        CLIENT_FILE.read_text(
            encoding="utf-8"
        )
    )

    installed = data.get("installed")

    if not isinstance(installed, dict):
        raise GmailConnectionError(
            "OAuth client is not a Desktop app client."
        )

    client_id = str(
        installed.get("client_id", "")
    ).strip()

    client_secret = str(
        installed.get("client_secret", "")
    ).strip()

    token_uri = str(
        installed.get(
            "token_uri",
            "https://oauth2.googleapis.com/token",
        )
    ).strip()

    if not client_id or not client_secret:
        raise GmailConnectionError(
            "OAuth client configuration is incomplete."
        )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "token_uri": token_uri,
    }


def _store_refresh_token(
    refresh_token: str,
) -> None:
    if not refresh_token:
        raise GmailConnectionError(
            "Google returned no refresh token."
        )

    keyring.set_password(
        KEYRING_SERVICE,
        KEYRING_KEY,
        refresh_token,
    )


def _load_refresh_token() -> str | None:
    value = keyring.get_password(
        KEYRING_SERVICE,
        KEYRING_KEY,
    )

    if not value:
        return None

    value = str(value).strip()

    return value or None


def _credentials_from_refresh_token(
    refresh_token: str,
) -> Credentials:
    client = _client_configuration()

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=client["token_uri"],
        client_id=client["client_id"],
        client_secret=client["client_secret"],
        scopes=SCOPES,
    )

    credentials.refresh(
        Request()
    )

    if not credentials.valid:
        raise GmailConnectionError(
            "Stored Gmail authorization could not be refreshed."
        )

    return credentials


def _gmail_profile(
    credentials: Credentials,
) -> dict[str, Any]:
    if not credentials.token:
        raise GmailConnectionError(
            "No Gmail access token is available."
        )

    request = urllib.request.Request(
        PROFILE_URL,
        method="GET",
        headers={
            "Authorization": (
                "Bearer " + credentials.token
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

    except urllib.error.HTTPError as error:
        raise GmailConnectionError(
            "Gmail API rejected the request. "
            f"http_status={error.code}"
        ) from error

    if not isinstance(profile, dict):
        raise GmailConnectionError(
            "Gmail API returned invalid profile data."
        )

    account = str(
        profile.get(
            "emailAddress",
            "",
        )
    ).strip()

    if not account:
        raise GmailConnectionError(
            "Gmail API returned no account identity."
        )

    return profile


def _authorize_once() -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_FILE),
        scopes=SCOPES,
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
        success_message=(
            "Data Platform is connected to Gmail. "
            "You can close this browser window."
        ),
    )

    if not credentials.refresh_token:
        raise GmailConnectionError(
            "Google returned no refresh token."
        )

    _store_refresh_token(
        credentials.refresh_token
    )

    return credentials



def restore_credentials() -> Credentials:
    """
    Rebuild credentials from the stored refresh token.

    Opens no browser: a caller that needs mail should fail with a
    clear message rather than block on a consent flow.
    """

    refresh_token = _load_refresh_token()

    if not refresh_token:
        raise GmailConnectionError(
            "No stored Gmail refresh credential."
        )

    return _credentials_from_refresh_token(refresh_token)


def restore_connection() -> dict[str, Any]:
    """
    Report whether a stored credential still reaches Gmail.

    Opens no browser. A caller asking "is an account connected" must
    be able to get a no without a consent flow blocking it, so every
    failure returns a status rather than raising.
    """

    try:
        credentials = restore_credentials()
    except GmailConnectionError:
        return {
            "status": "disconnected",
            "account": None,
            "browser_authorization": False,
            "connection_restored": False,
            "refresh_token_stored": False,
            "gmail_api_access": False,
        }

    try:
        profile = _gmail_profile(credentials)
    except Exception as error:
        # The credential exists but Gmail refused it: an expired
        # grant, a revoked token, a disabled API. Reporting that as
        # "no account" would hide a condition the user can fix, and
        # a caller reading only a count would show zero unread.
        return {
            "status": "unavailable",
            "account": None,
            "browser_authorization": False,
            "connection_restored": True,
            "refresh_token_stored": True,
            "gmail_api_access": False,
            "error_type": type(error).__name__,
        }

    return {
        "status": "connected",
        "account": profile.get("emailAddress"),
        "browser_authorization": False,
        "connection_restored": True,
        "refresh_token_stored": True,
        "gmail_api_access": True,
        "messages_total": profile.get("messagesTotal"),
        "threads_total": profile.get("threadsTotal"),
    }

def connect() -> dict[str, Any]:
    refresh_token = _load_refresh_token()

    browser_authorization = False
    connection_restored = False

    if refresh_token:
        try:
            credentials = (
                _credentials_from_refresh_token(
                    refresh_token
                )
            )

            connection_restored = True

        except Exception:
            credentials = _authorize_once()
            browser_authorization = True

    else:
        credentials = _authorize_once()
        browser_authorization = True

    profile = _gmail_profile(
        credentials
    )

    return {
        "status": "connected",
        "account": profile["emailAddress"],
        "browser_authorization": browser_authorization,
        "connection_restored": connection_restored,
        "refresh_token_stored": bool(
            _load_refresh_token()
        ),
        "gmail_api_access": True,
        "messages_total": profile.get(
            "messagesTotal",
            0,
        ),
        "threads_total": profile.get(
            "threadsTotal",
            0,
        ),
    }

def gmail_profile(
    credentials: Credentials,
) -> dict[str, Any]:
    """
    Public interface to the existing Gmail profile operation.

    The credential must already be restored. This function does
    not initiate browser authorization.
    """
    return _gmail_profile(
        credentials
    )

