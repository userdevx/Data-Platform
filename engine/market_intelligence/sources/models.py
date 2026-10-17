from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


StrictOptionalBool = Optional[
    bool
]


@dataclass(
    frozen=True,
    slots=True,
)
class InformationSource:
    """
    Durable policy and capability description for an
    external information provider.

    This model does not:
    - make network requests;
    - collect information;
    - write Data Engine records;
    - perform analysis;
    - run models.

    Unknown policy information is represented by None.

    None must never be interpreted as permission.
    """

    source_id: str

    name: str

    source_type: str

    authority: str

    domains: tuple[
        str,
        ...,
    ]

    registered: bool

    enabled: bool

    collector_implemented: bool

    ingestion_enabled: bool

    cost_free: StrictOptionalBool

    authentication_required: StrictOptionalBool

    api_available: StrictOptionalBool

    stream_available: StrictOptionalBool

    bulk_download_available: StrictOptionalBool

    raw_storage_allowed: StrictOptionalBool

    commercial_use_allowed: StrictOptionalBool

    raw_redistribution_allowed: StrictOptionalBool

    derived_analysis_allowed: StrictOptionalBool

    model_training_allowed: StrictOptionalBool

    attribution_required: StrictOptionalBool

    share_alike_required: StrictOptionalBool

    license_name: str | None

    source_url: str

    documentation_url: str

    api_url: str | None = None

    stream_url: str | None = None

    bulk_url: str | None = None

    def __post_init__(
        self,
    ) -> None:
        required_text = {
            "source_id": (
                self.source_id
            ),
            "name": (
                self.name
            ),
            "source_type": (
                self.source_type
            ),
            "authority": (
                self.authority
            ),
            "source_url": (
                self.source_url
            ),
            "documentation_url": (
                self.documentation_url
            ),
        }

        for (
            field_name,
            value,
        ) in required_text.items():
            self._require_text(
                value,
                field_name=field_name,
            )

        if not isinstance(
            self.domains,
            tuple,
        ):
            raise TypeError(
                "domains must be a tuple."
            )

        if not self.domains:
            raise ValueError(
                "domains cannot be empty."
            )

        for domain in self.domains:
            self._require_text(
                domain,
                field_name="domain",
            )

        strict_bool_fields = {
            "registered": (
                self.registered
            ),
            "enabled": (
                self.enabled
            ),
            "collector_implemented": (
                self.collector_implemented
            ),
            "ingestion_enabled": (
                self.ingestion_enabled
            ),
        }

        for (
            field_name,
            value,
        ) in strict_bool_fields.items():
            if type(
                value
            ) is not bool:
                raise TypeError(
                    f"{field_name} must be bool."
                )

        optional_bool_fields = {
            "cost_free": (
                self.cost_free
            ),
            "authentication_required": (
                self.authentication_required
            ),
            "api_available": (
                self.api_available
            ),
            "stream_available": (
                self.stream_available
            ),
            "bulk_download_available": (
                self.bulk_download_available
            ),
            "raw_storage_allowed": (
                self.raw_storage_allowed
            ),
            "commercial_use_allowed": (
                self.commercial_use_allowed
            ),
            "raw_redistribution_allowed": (
                self.raw_redistribution_allowed
            ),
            "derived_analysis_allowed": (
                self.derived_analysis_allowed
            ),
            "model_training_allowed": (
                self.model_training_allowed
            ),
            "attribution_required": (
                self.attribution_required
            ),
            "share_alike_required": (
                self.share_alike_required
            ),
        }

        for (
            field_name,
            value,
        ) in optional_bool_fields.items():
            if (
                value is not None
                and type(
                    value
                )
                is not bool
            ):
                raise TypeError(
                    f"{field_name} must be "
                    "bool or None."
                )

        optional_text = {
            "license_name": (
                self.license_name
            ),
            "api_url": (
                self.api_url
            ),
            "stream_url": (
                self.stream_url
            ),
            "bulk_url": (
                self.bulk_url
            ),
        }

        for (
            field_name,
            value,
        ) in optional_text.items():
            if value is None:
                continue

            self._require_text(
                value,
                field_name=field_name,
            )

    @staticmethod
    def _require_text(
        value: object,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be str."
            )

        normalized = (
            value.strip()
        )

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized
