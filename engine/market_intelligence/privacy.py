from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarketPrivacyPolicy:
    allow_identity_metadata: bool = False


class MetadataSanitizer:
    _identity_fields = {
        "account_id",
        "author_id",
        "display_name",
        "email",
        "handle",
        "phone",
        "profile_id",
        "screen_name",
        "user_id",
        "username",
    }

    def __init__(
        self,
        policy: MarketPrivacyPolicy | None = None,
    ) -> None:
        self.policy = (
            policy
            or MarketPrivacyPolicy()
        )

    def sanitize(
        self,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if self.policy.allow_identity_metadata:
            return dict(metadata)

        return {
            key: value
            for key, value in metadata.items()
            if key.strip().lower()
            not in self._identity_fields
        }
