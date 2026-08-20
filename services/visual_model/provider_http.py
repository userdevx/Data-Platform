from __future__ import annotations

import json
import os
from typing import Any, Mapping
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)

from services.visual_model.provider_errors import (
    VisualProviderRequestError,
    VisualProviderResponseError,
)


def resolve_credential(
    credential_reference: str,
) -> str:
    reference = credential_reference.strip()

    if not reference:
        return ""

    credential = os.environ.get(
        reference,
        "",
    ).strip()

    if not credential:
        raise VisualProviderRequestError(
            "The configured provider credential "
            "is unavailable."
        )

    return credential


def request_json(
    *,
    method: str,
    url: str,
    timeout_seconds: int,
    headers: Mapping[str, str],
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        **dict(headers),
    }

    encoded_payload: bytes | None = None

    if payload is not None:
        request_headers[
            "Content-Type"
        ] = "application/json"

        try:
            encoded_payload = json.dumps(
                dict(payload),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (
            TypeError,
            ValueError,
        ) as error:
            raise VisualProviderRequestError(
                "The provider request could not "
                "be encoded."
            ) from error

    request = Request(
        url=url,
        data=encoded_payload,
        headers=request_headers,
        method=method.upper(),
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            response_data = response.read()
    except HTTPError as error:
        if error.code in {
            401,
            403,
        }:
            raise VisualProviderRequestError(
                "The provider rejected authentication."
            ) from error

        raise VisualProviderRequestError(
            "The provider returned HTTP status "
            f"{error.code}."
        ) from error
    except URLError as error:
        raise VisualProviderRequestError(
            "The provider could not be reached."
        ) from error
    except OSError as error:
        raise VisualProviderRequestError(
            "The provider request failed."
        ) from error

    try:
        decoded = json.loads(
            response_data.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise VisualProviderResponseError(
            "The provider returned invalid JSON."
        ) from error

    if not isinstance(decoded, dict):
        raise VisualProviderResponseError(
            "The provider response must be an object."
        )

    return decoded
