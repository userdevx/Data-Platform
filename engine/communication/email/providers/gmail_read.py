from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from engine.communication.gmail_api_connection import (
    GmailConnectionError,
    gmail_profile,
    restore_credentials,
)


DEFAULT_CONFIG_PATH = Path(
    "config/communication/email.json"
)

GMAIL_API_ROOT = (
    "https://gmail.googleapis.com/gmail/v1"
)


class EmailConfigurationError(ValueError):
    """Email read configuration is invalid."""


class EmailReadError(RuntimeError):
    """A bounded Gmail API read operation failed."""


def _load_config(
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, int]:
    config_path = Path(path)

    if not config_path.is_file():
        raise EmailConfigurationError(
            "Email configuration file was not found: "
            + str(config_path)
        )

    try:
        payload = json.loads(
            config_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise EmailConfigurationError(
            "Email configuration could not be read. "
            f"error_type={type(error).__name__}"
        ) from error

    if not isinstance(payload, dict):
        raise EmailConfigurationError(
            "Email configuration must contain a JSON object."
        )

    read_config = payload.get("read")

    if isinstance(read_config, dict):
        raw_max_messages = read_config.get(
            "max_messages",
            10,
        )
    else:
        legacy_config = payload.get(
            "imap",
            {},
        )

        if isinstance(legacy_config, dict):
            raw_max_messages = legacy_config.get(
                "max_messages",
                10,
            )
        else:
            raw_max_messages = 10

    try:
        max_messages = int(
            raw_max_messages
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise EmailConfigurationError(
            "max_messages must be an integer."
        ) from error

    if not 1 <= max_messages <= 100:
        raise EmailConfigurationError(
            "max_messages must be between 1 and 100."
        )

    return {
        "max_messages": max_messages,
    }


def _gmail_get_json(
    *,
    url: str,
    access_token: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method="GET",
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
            payload = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except urllib.error.HTTPError as error:
        raise EmailReadError(
            "Gmail API rejected the request. "
            f"http_status={error.code}"
        ) from error

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise EmailReadError(
            "Gmail API request failed. "
            f"error_type={type(error).__name__}"
        ) from error

    if not isinstance(payload, dict):
        raise EmailReadError(
            "Gmail API returned invalid data."
        )

    return payload


def _header_map(
    payload: dict[str, Any],
) -> dict[str, str]:
    headers = payload.get(
        "headers",
        [],
    )

    if not isinstance(headers, list):
        return {}

    result: dict[str, str] = {}

    for header in headers:
        if not isinstance(header, dict):
            continue

        name = str(
            header.get(
                "name",
                "",
            )
        ).strip().lower()

        value = str(
            header.get(
                "value",
                "",
            )
        ).strip()

        if name:
            result[name] = value

    return result


def _message_metadata(
    *,
    message_id: str,
    access_token: str,
) -> dict[str, Any]:
    parameters = urllib.parse.urlencode(
        [
            ("format", "metadata"),
            ("metadataHeaders", "Message-ID"),
            ("metadataHeaders", "From"),
            ("metadataHeaders", "To"),
            ("metadataHeaders", "Subject"),
            ("metadataHeaders", "Date"),
        ]
    )

    url = (
        GMAIL_API_ROOT
        + "/users/me/messages/"
        + urllib.parse.quote(
            message_id,
            safe="",
        )
        + "?"
        + parameters
    )

    message = _gmail_get_json(
        url=url,
        access_token=access_token,
    )

    payload = message.get(
        "payload",
        {},
    )

    if not isinstance(payload, dict):
        payload = {}

    labels = message.get(
        "labelIds",
        [],
    )

    if not isinstance(labels, list):
        labels = []

    headers = _header_map(
        payload
    )

    return {
        "id": str(
            message.get(
                "id",
                "",
            )
        ),
        "thread_id": str(
            message.get(
                "threadId",
                "",
            )
        ),
        "message_id": headers.get(
            "message-id",
            "",
        ),
        "from": headers.get(
            "from",
            "",
        ),
        "to": headers.get(
            "to",
            "",
        ),
        "subject": headers.get(
            "subject",
            "",
        ),
        "date": headers.get(
            "date",
            "",
        ),
        "unread": "UNREAD" in labels,
    }


def read_unread_email(
    *,
    account: str,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    requested_account = str(
        account or ""
    ).strip()

    if not requested_account:
        raise ValueError(
            "account is required."
        )

    config = _load_config(
        config_path
    )

    try:
        credentials = restore_credentials()

        profile = gmail_profile(
            credentials
        )
    except GmailConnectionError as error:
        raise EmailReadError(
            "Existing Gmail connection could not be restored."
        ) from error

    connected_account = str(
        profile.get(
            "emailAddress",
            "",
        )
    ).strip()

    if not connected_account:
        raise EmailReadError(
            "Gmail profile returned no account."
        )

    if (
        connected_account.casefold()
        != requested_account.casefold()
    ):
        raise EmailReadError(
            "Connected Gmail account does not match "
            "the requested account."
        )

    access_token = str(
        credentials.token or ""
    ).strip()

    if not access_token:
        raise EmailReadError(
            "Restored Gmail connection returned no access token."
        )

    parameters = urllib.parse.urlencode(
        [
            ("labelIds", "INBOX"),
            ("labelIds", "UNREAD"),
            (
                "maxResults",
                str(
                    config["max_messages"]
                ),
            ),
            (
                "includeSpamTrash",
                "false",
            ),
        ]
    )

    list_url = (
        GMAIL_API_ROOT
        + "/users/me/messages?"
        + parameters
    )

    listing = _gmail_get_json(
        url=list_url,
        access_token=access_token,
    )

    references = listing.get(
        "messages",
        [],
    )

    if not isinstance(references, list):
        references = []

    messages: list[
        dict[str, Any]
    ] = []

    for reference in references:
        if not isinstance(reference, dict):
            continue

        message_id = str(
            reference.get(
                "id",
                "",
            )
        ).strip()

        if not message_id:
            continue

        metadata = _message_metadata(
            message_id=message_id,
            access_token=access_token,
        )

        if metadata["unread"]:
            messages.append(
                metadata
            )

    estimate = listing.get(
        "resultSizeEstimate",
        len(messages),
    )

    try:
        unread_count = int(
            estimate
        )
    except (
        TypeError,
        ValueError,
    ):
        unread_count = len(
            messages
        )

    return {
        "status": "ok",
        "provider": "gmail_api",
        "account": connected_account,
        "mailbox": "INBOX",
        "connection_restored": True,
        "browser_authorization": False,
        "gmail_api_access": True,
        "messages_listed": True,
        "unread_count": unread_count,
        "unread_count_is_estimate": True,
        "returned_count": len(
            messages
        ),
        "max_messages": config[
            "max_messages"
        ],
        "body_fetched": False,
        "messages": messages,
    }



def read_recent_email(
    *,
    account: str,
    limit: int = 1,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    requested_account = str(
        account or ""
    ).strip()

    if not requested_account:
        raise ValueError(
            "account is required."
        )

    try:
        requested_limit = int(
            limit
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "limit must be an integer."
        ) from error

    requested_limit = max(
        1,
        min(
            20,
            requested_limit,
        ),
    )

    _load_config(
        config_path
    )

    try:
        credentials = restore_credentials()

        profile = gmail_profile(
            credentials
        )
    except GmailConnectionError as error:
        raise EmailReadError(
            "Existing email connection could not be restored."
        ) from error

    connected_account = str(
        profile.get(
            "emailAddress",
            "",
        )
    ).strip()

    if not connected_account:
        raise EmailReadError(
            "Connected account information is unavailable."
        )

    if (
        connected_account.casefold()
        != requested_account.casefold()
    ):
        raise EmailReadError(
            "Connected account does not match "
            "the requested account."
        )

    access_token = str(
        credentials.token or ""
    ).strip()

    if not access_token:
        raise EmailReadError(
            "Restored connection returned no access token."
        )

    parameters = urllib.parse.urlencode(
        [
            (
                "labelIds",
                "INBOX",
            ),
            (
                "maxResults",
                str(
                    requested_limit
                ),
            ),
            (
                "includeSpamTrash",
                "false",
            ),
        ]
    )

    list_url = (
        GMAIL_API_ROOT
        + "/users/me/messages?"
        + parameters
    )

    listing = _gmail_get_json(
        url=list_url,
        access_token=access_token,
    )

    references = listing.get(
        "messages",
        [],
    )

    if not isinstance(
        references,
        list,
    ):
        references = []

    messages: list[
        dict[str, Any]
    ] = []

    for reference in references:
        if not isinstance(
            reference,
            dict,
        ):
            continue

        message_id = str(
            reference.get(
                "id",
                "",
            )
        ).strip()

        if not message_id:
            continue

        messages.append(
            _message_metadata(
                message_id=message_id,
                access_token=access_token,
            )
        )

        if len(messages) >= requested_limit:
            break

    return {
        "status": "ok",
        "account": connected_account,
        "mailbox": "INBOX",
        "messages_listed": True,
        "returned_count": len(
            messages
        ),
        "body_fetched": False,
        "messages": messages,
    }
