from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
)
from dataclasses import dataclass
from typing import Any

from engine.market_intelligence.sources.base import (
    PublicSource,
)
from engine.market_intelligence.sources.catalog import (
    INFORMATION_SOURCES,
)
from engine.market_intelligence.sources.census import (
    CensusSource,
)
from engine.market_intelligence.sources.registry import (
    InformationSourceRegistry,
    PublicSourceRegistry,
)


@dataclass(
    frozen=True,
    slots=True,
)
class SourceRuntimeConfiguration:
    """
    Runtime configuration for one executable
    information-source adapter.

    Source identity and policy remain owned by the
    information-source catalog.

    Runtime-specific settings such as dataset paths
    and geography are supplied here instead of being
    hardcoded into the source catalog.
    """

    source_id: str
    options: Mapping[
        str,
        Any,
    ]

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.source_id,
            str,
        ):
            raise TypeError(
                "source_id must be a string."
            )

        normalized_source_id = (
            self.source_id
            .strip()
            .casefold()
        )

        if not normalized_source_id:
            raise ValueError(
                "source_id cannot be empty."
            )

        if not isinstance(
            self.options,
            Mapping,
        ):
            raise TypeError(
                "options must be a mapping."
            )

        normalized_options: dict[
            str,
            Any,
        ] = {}

        for key, value in (
            self.options.items()
        ):
            if not isinstance(
                key,
                str,
            ):
                raise TypeError(
                    "Runtime option names "
                    "must be strings."
                )

            normalized_key = (
                key.strip()
            )

            if not normalized_key:
                raise ValueError(
                    "Runtime option names "
                    "cannot be empty."
                )

            normalized_options[
                normalized_key
            ] = value

        object.__setattr__(
            self,
            "source_id",
            normalized_source_id,
        )

        object.__setattr__(
            self,
            "options",
            normalized_options,
        )


SourceFactory = Callable[
    [
        Mapping[
            str,
            Any,
        ]
    ],
    PublicSource,
]


def _build_census_source(
    options: Mapping[
        str,
        Any,
    ],
) -> PublicSource:
    allowed_options = {
        "dataset_path",
        "geography",
        "api_base_url",
        "api_key_environment_name",
        "env_path",
        "timeout_seconds",
        "max_response_bytes",
    }

    provided_options = set(
        options
    )

    unknown_options = (
        provided_options
        - allowed_options
    )

    if unknown_options:
        raise ValueError(
            "Unsupported Census runtime "
            "options: "
            f"{sorted(unknown_options)}"
        )

    required_options = {
        "dataset_path",
        "geography",
    }

    missing_options = (
        required_options
        - provided_options
    )

    if missing_options:
        raise ValueError(
            "Missing Census runtime "
            "options: "
            f"{sorted(missing_options)}"
        )

    return CensusSource(
        **dict(
            options
        )
    )


_SOURCE_FACTORIES: dict[
    str,
    SourceFactory,
] = {
    "census": (
        _build_census_source
    ),
}


def build_public_source_registry(
    configurations: tuple[
        SourceRuntimeConfiguration,
        ...,
    ],
    *,
    information_registry: (
        InformationSourceRegistry
        | None
    ) = None,
) -> PublicSourceRegistry:
    """
    Build the executable PublicSourceRegistry from
    explicit runtime configuration.

    A source may be instantiated only when its
    information-source catalog record says it is:

        registered
        enabled
        collector_implemented
        ingestion_enabled

    Source rights and policy metadata remain separate
    from executable adapter construction.
    """

    if not isinstance(
        configurations,
        tuple,
    ):
        raise TypeError(
            "configurations must be a tuple."
        )

    policy_registry = (
        information_registry
        if information_registry
        is not None
        else InformationSourceRegistry(
            INFORMATION_SOURCES
        )
    )

    executable_registry = (
        PublicSourceRegistry()
    )

    configured_source_ids: set[
        str
    ] = set()

    for configuration in configurations:
        if not isinstance(
            configuration,
            SourceRuntimeConfiguration,
        ):
            raise TypeError(
                "Each configuration must be a "
                "SourceRuntimeConfiguration."
            )

        source_id = (
            configuration.source_id
        )

        if (
            source_id
            in configured_source_ids
        ):
            raise ValueError(
                "Duplicate runtime source "
                f"configuration: {source_id}"
            )

        configured_source_ids.add(
            source_id
        )

        definition = (
            policy_registry.get(
                source_id
            )
        )

        if not (
            definition.registered
            and definition.enabled
            and definition.collector_implemented
            and definition.ingestion_enabled
        ):
            raise RuntimeError(
                "Source is not enabled for "
                "runtime ingestion: "
                f"{source_id}"
            )

        factory = (
            _SOURCE_FACTORIES.get(
                source_id
            )
        )

        if factory is None:
            raise RuntimeError(
                "No executable source adapter "
                "is registered for: "
                f"{source_id}"
            )

        executable_source = (
            factory(
                configuration.options
            )
        )

        if (
            executable_source.source_name
            != definition.name
        ):
            raise RuntimeError(
                "Executable source identity "
                "does not match catalog "
                f"definition: {source_id}"
            )

        executable_registry.register(
            executable_source
        )

    return executable_registry
