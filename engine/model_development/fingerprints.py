from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint_payload(
    payload: Any,
) -> str:
    """
    Create a deterministic SHA-256 fingerprint for
    JSON-serializable information.

    Dictionary ordering and formatting whitespace do
    not affect the resulting fingerprint.
    """

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()
