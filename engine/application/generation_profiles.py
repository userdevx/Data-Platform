"""Per-capability generation limits for local text models.

The values come from generation_profiles.json beside the model registry.
A capability without an entry uses the "default" entry. A missing file
keeps the behaviour that was in force before profiles existed, so chat
answers do not change unless the configuration changes them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from services.visual_model.provider_errors import (
    VisualProviderConfigurationError,
)


@dataclass(frozen=True)
class GenerationProfile:
    name: str
    num_predict: int
    num_ctx: int
    stream: bool = False
    reject_truncated: bool = False
    idle_timeout_seconds: int | None = None
    total_timeout_seconds: int | None = None


PROFILE_FIELDS = tuple(
    item.name
    for item in fields(GenerationProfile)
    if item.name != "name"
)

INTEGER_FIELDS = (
    "num_predict",
    "num_ctx",
    "idle_timeout_seconds",
    "total_timeout_seconds",
)

BOOLEAN_FIELDS = (
    "stream",
    "reject_truncated",
)

# The request options that were in force before profiles existed.
PRE_PROFILE_BEHAVIOUR = GenerationProfile(
    name="pre_profile",
    num_predict=384,
    num_ctx=8192,
)


def _merge(
    base: GenerationProfile,
    entry: Any,
    *,
    source: str,
    name: str,
) -> GenerationProfile:
    if not isinstance(entry, dict):
        raise VisualProviderConfigurationError(
            f"Generation profile {source} must be an object."
        )

    unknown = sorted(set(entry) - set(PROFILE_FIELDS))

    if unknown:
        raise VisualProviderConfigurationError(
            f"Generation profile {source} has unknown fields: "
            + ", ".join(unknown)
        )

    values = {
        field: getattr(base, field)
        for field in PROFILE_FIELDS
    }

    for field in INTEGER_FIELDS:
        if field not in entry:
            continue

        value = entry[field]

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
        ):
            raise VisualProviderConfigurationError(
                f"Generation profile {source}.{field} "
                "must be a positive integer."
            )

        values[field] = value

    for field in BOOLEAN_FIELDS:
        if field not in entry:
            continue

        if not isinstance(entry[field], bool):
            raise VisualProviderConfigurationError(
                f"Generation profile {source}.{field} "
                "must be true or false."
            )

        values[field] = entry[field]

    profile = GenerationProfile(name=name, **values)

    if profile.num_predict >= profile.num_ctx:
        raise VisualProviderConfigurationError(
            f"Generation profile {source}: num_predict must be "
            "smaller than num_ctx, or the prompt has no room."
        )

    if profile.stream and (
        profile.idle_timeout_seconds is None
        or profile.total_timeout_seconds is None
    ):
        raise VisualProviderConfigurationError(
            f"Generation profile {source}: streaming requires "
            "idle_timeout_seconds and total_timeout_seconds."
        )

    if (
        profile.idle_timeout_seconds is not None
        and profile.total_timeout_seconds is not None
        and profile.idle_timeout_seconds
        > profile.total_timeout_seconds
    ):
        raise VisualProviderConfigurationError(
            f"Generation profile {source}: idle_timeout_seconds "
            "cannot exceed total_timeout_seconds."
        )

    return profile


def load_generation_profile(
    path: Path,
    capability: str,
) -> GenerationProfile:
    path = Path(path)

    if not path.exists():
        return PRE_PROFILE_BEHAVIOUR

    try:
        document = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        raise VisualProviderConfigurationError(
            "The generation profile configuration "
            "could not be read."
        ) from error

    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
    ):
        raise VisualProviderConfigurationError(
            "The generation profile configuration "
            "requires schema_version 1."
        )

    default = _merge(
        PRE_PROFILE_BEHAVIOUR,
        document.get("default", {}),
        source="default",
        name="default",
    )

    capabilities = document.get("capabilities", {})

    if not isinstance(capabilities, dict):
        raise VisualProviderConfigurationError(
            "Generation profile capabilities "
            "must be an object."
        )

    # Validate every entry, so a broken entry is reported even when
    # the current request does not use it.
    profiles = {
        str(key).strip().lower(): _merge(
            default,
            entry,
            source=f"capabilities.{key}",
            name=str(key).strip().lower(),
        )
        for key, entry in capabilities.items()
    }

    return profiles.get(
        capability.strip().lower(),
        default,
    )
