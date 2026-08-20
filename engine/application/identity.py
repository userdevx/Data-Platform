from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class ApplicationIdentityError(RuntimeError):
    """Raised when an application identity definition is invalid."""


@dataclass(frozen=True)
class ApplicationIdentity:
    definition_version: int
    display_name: str
    short_name: str
    description: str
    tagline: str
    window_title: str
    navigation_title: str
    home_heading: str
    loading_message: str
    ready_message: str
    logo_text: str
    accent_name: str
    executable_name: str
    package_name: str
    bundle_identifier: str
    product_family: str
    configuration_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_version": self.definition_version,
            "identity": {
                "display_name": self.display_name,
                "short_name": self.short_name,
                "description": self.description,
                "tagline": self.tagline,
            },
            "interface": {
                "window_title": self.window_title,
                "navigation_title": self.navigation_title,
                "home_heading": self.home_heading,
                "loading_message": self.loading_message,
                "ready_message": self.ready_message,
            },
            "branding": {
                "logo_text": self.logo_text,
                "accent_name": self.accent_name,
            },
            "package": {
                "executable_name": self.executable_name,
                "package_name": self.package_name,
                "bundle_identifier": self.bundle_identifier,
            },
            "metadata": {
                "product_family": self.product_family,
                "configuration_status": self.configuration_status,
            },
        }


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def active_definition_path() -> Path:
    return (
        project_root()
        / "config"
        / "application"
        / "active.json"
    )


def require_mapping(
    value: object,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApplicationIdentityError(
            f"{field_name} must be an object."
        )

    return value


def require_text(
    mapping: dict[str, Any],
    field_name: str,
) -> str:
    value = mapping.get(field_name)

    if not isinstance(value, str):
        raise ApplicationIdentityError(
            f"{field_name} must be a string."
        )

    normalized = " ".join(value.split())

    if not normalized:
        raise ApplicationIdentityError(
            f"{field_name} cannot be empty."
        )

    return normalized


def require_positive_integer(
    mapping: dict[str, Any],
    field_name: str,
) -> int:
    value = mapping.get(field_name)

    if not isinstance(value, int) or value < 1:
        raise ApplicationIdentityError(
            f"{field_name} must be a positive integer."
        )

    return value


def load_application_identity(
    definition_path: Path | None = None,
) -> ApplicationIdentity:
    path = definition_path or active_definition_path()

    if not path.is_file():
        raise ApplicationIdentityError(
            "The active application definition was not found."
        )

    try:
        raw = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ApplicationIdentityError(
            "The active application definition contains invalid JSON."
        ) from exc

    root = require_mapping(
        raw,
        "definition",
    )
    identity = require_mapping(
        root.get("identity"),
        "identity",
    )
    interface = require_mapping(
        root.get("interface"),
        "interface",
    )
    branding = require_mapping(
        root.get("branding"),
        "branding",
    )
    package = require_mapping(
        root.get("package"),
        "package",
    )
    metadata = require_mapping(
        root.get("metadata"),
        "metadata",
    )

    configuration_status = require_text(
        metadata,
        "configuration_status",
    )

    if configuration_status != "active":
        raise ApplicationIdentityError(
            "The application definition is not active."
        )

    return ApplicationIdentity(
        definition_version=require_positive_integer(
            root,
            "definition_version",
        ),
        display_name=require_text(
            identity,
            "display_name",
        ),
        short_name=require_text(
            identity,
            "short_name",
        ),
        description=require_text(
            identity,
            "description",
        ),
        tagline=require_text(
            identity,
            "tagline",
        ),
        window_title=require_text(
            interface,
            "window_title",
        ),
        navigation_title=require_text(
            interface,
            "navigation_title",
        ),
        home_heading=require_text(
            interface,
            "home_heading",
        ),
        loading_message=require_text(
            interface,
            "loading_message",
        ),
        ready_message=require_text(
            interface,
            "ready_message",
        ),
        logo_text=require_text(
            branding,
            "logo_text",
        ),
        accent_name=require_text(
            branding,
            "accent_name",
        ),
        executable_name=require_text(
            package,
            "executable_name",
        ),
        package_name=require_text(
            package,
            "package_name",
        ),
        bundle_identifier=require_text(
            package,
            "bundle_identifier",
        ),
        product_family=require_text(
            metadata,
            "product_family",
        ),
        configuration_status=configuration_status,
    )
