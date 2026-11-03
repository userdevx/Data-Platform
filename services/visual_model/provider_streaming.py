from __future__ import annotations

import http.client
import json
import socket
import time
from typing import Any, Callable, Mapping
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


def stream_json_lines(
    *,
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    idle_timeout_seconds: int,
    total_timeout_seconds: int,
    on_line: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """
    POST a JSON payload and read a newline-delimited JSON response.

    idle_timeout_seconds bounds the wait for each line, including the
    first one, which a local model only sends after it has read the
    whole prompt. total_timeout_seconds bounds the whole exchange, so
    a model that keeps producing output still cannot run forever.

    Returns the final object, the one with done set to true.
    """

    try:
        body = json.dumps(
            dict(payload),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise VisualProviderRequestError(
            "The provider request could not be encoded."
        ) from error

    request = Request(
        url=url,
        data=body,
        headers={
            "Accept": "application/x-ndjson",
            "Content-Type": "application/json",
            **dict(headers),
        },
        method="POST",
    )

    deadline = time.monotonic() + total_timeout_seconds

    try:
        with urlopen(
            request,
            timeout=idle_timeout_seconds,
        ) as response:
            for raw_line in response:
                if time.monotonic() > deadline:
                    raise VisualProviderRequestError(
                        "The provider did not finish within "
                        f"{total_timeout_seconds} seconds."
                    )

                line = raw_line.strip()

                if not line:
                    continue

                try:
                    item = json.loads(line.decode("utf-8"))
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                ) as error:
                    raise VisualProviderResponseError(
                        "The provider stream contained "
                        "invalid JSON."
                    ) from error

                if not isinstance(item, dict):
                    raise VisualProviderResponseError(
                        "The provider stream must contain "
                        "objects."
                    )

                if item.get("error"):
                    raise VisualProviderResponseError(
                        "The provider reported an error: "
                        + str(item["error"])[:300]
                    )

                on_line(item)

                if item.get("done") is True:
                    return item

    except (
        VisualProviderRequestError,
        VisualProviderResponseError,
    ):
        raise
    except HTTPError as error:
        if error.code in {401, 403}:
            raise VisualProviderRequestError(
                "The provider rejected authentication."
            ) from error

        raise VisualProviderRequestError(
            "The provider returned HTTP status "
            f"{error.code}."
        ) from error
    except (TimeoutError, socket.timeout) as error:
        raise VisualProviderRequestError(
            "The provider sent no output for "
            f"{idle_timeout_seconds} seconds."
        ) from error
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise VisualProviderRequestError(
                "The provider sent no output for "
                f"{idle_timeout_seconds} seconds."
            ) from error

        raise VisualProviderRequestError(
            "The provider could not be reached."
        ) from error
    except (OSError, http.client.HTTPException) as error:
        raise VisualProviderRequestError(
            "The provider request failed."
        ) from error

    raise VisualProviderResponseError(
        "The provider stream ended before completion."
    )
