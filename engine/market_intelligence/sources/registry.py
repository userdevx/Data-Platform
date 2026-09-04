from __future__ import annotations

from engine.market_intelligence.sources.base import (
    PublicSource,
)
from engine.market_intelligence.sources.models import (
    InformationSource,
)


class PublicSourceRegistry:
    """
    Runtime registry for executable external-source
    adapters.

    This existing registry remains separate from source
    policy metadata.
    """

    def __init__(
        self,
    ) -> None:
        self._sources: dict[
            str,
            PublicSource,
        ] = {}

    def register(
        self,
        source: PublicSource,
    ) -> None:
        key = self._normalize_name(
            source.source_name
        )

        self._sources[
            key
        ] = source

    def unregister(
        self,
        source_name: str,
    ) -> None:
        key = self._normalize_name(
            source_name
        )

        self._sources.pop(
            key,
            None,
        )

    def get(
        self,
        source_name: str,
    ) -> PublicSource:
        key = self._normalize_name(
            source_name
        )

        try:
            return self._sources[
                key
            ]

        except KeyError as error:
            raise KeyError(
                "Source is not registered: "
                f"{source_name}"
            ) from error

    def has(
        self,
        source_name: str,
    ) -> bool:
        key = self._normalize_name(
            source_name
        )

        return (
            key
            in self._sources
        )

    def all(
        self,
    ) -> tuple[
        PublicSource,
        ...,
    ]:
        return tuple(
            self._sources[
                key
            ]
            for key in sorted(
                self._sources
            )
        )

    def available_sources(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        return tuple(
            sorted(
                self._sources
            )
        )

    @staticmethod
    def _normalize_name(
        source_name: str,
    ) -> str:
        if not isinstance(
            source_name,
            str,
        ):
            raise TypeError(
                "Source name must be a string."
            )

        normalized = (
            source_name
            .strip()
            .casefold()
        )

        if not normalized:
            raise ValueError(
                "Source name cannot be empty."
            )

        return normalized


class InformationSourceRegistry:
    """
    Deterministic registry containing source identity,
    access capabilities, collection state, and reviewed
    usage rights.

    This registry performs no network access and writes
    no Data Engine records.
    """

    def __init__(
        self,
        sources: tuple[
            InformationSource,
            ...,
        ] = (),
    ) -> None:
        if not isinstance(
            sources,
            tuple,
        ):
            raise TypeError(
                "sources must be a tuple."
            )

        self._sources: dict[
            str,
            InformationSource,
        ] = {}

        for source in sources:
            self.register(
                source
            )

    def register(
        self,
        source: InformationSource,
    ) -> None:
        if not isinstance(
            source,
            InformationSource,
        ):
            raise TypeError(
                "source must be an "
                "InformationSource."
            )

        key = self._normalize_id(
            source.source_id
        )

        if key in self._sources:
            raise ValueError(
                "Duplicate source_id: "
                f"{source.source_id}"
            )

        self._sources[
            key
        ] = source

    def get(
        self,
        source_id: str,
    ) -> InformationSource:
        key = self._normalize_id(
            source_id
        )

        try:
            return self._sources[
                key
            ]

        except KeyError as error:
            raise LookupError(
                "Unknown information source: "
                f"{source_id}"
            ) from error

    def has(
        self,
        source_id: str,
    ) -> bool:
        key = self._normalize_id(
            source_id
        )

        return (
            key
            in self._sources
        )

    def list_all(
        self,
    ) -> tuple[
        InformationSource,
        ...,
    ]:
        return tuple(
            self._sources[
                key
            ]
            for key in sorted(
                self._sources
            )
        )

    def list_enabled(
        self,
    ) -> tuple[
        InformationSource,
        ...,
    ]:
        return tuple(
            source
            for source
            in self.list_all()
            if (
                source.registered
                and source.enabled
            )
        )

    def list_collectible(
        self,
    ) -> tuple[
        InformationSource,
        ...,
    ]:
        return tuple(
            source
            for source
            in self.list_all()
            if (
                source.registered
                and source.enabled
                and source.collector_implemented
                and source.ingestion_enabled
            )
        )

    def list_training_eligible(
        self,
    ) -> tuple[
        InformationSource,
        ...,
    ]:
        """
        Return sources whose reviewed source-level
        training policy explicitly permits training.

        This does not make individual records training
        eligible. Record-level provenance, quality,
        Evidence, validation, and dataset policy are
        separate gates.
        """

        return tuple(
            source
            for source
            in self.list_all()
            if (
                source.registered
                and (
                    source
                    .model_training_allowed
                    is True
                )
            )
        )

    def list_commercially_usable(
        self,
    ) -> tuple[
        InformationSource,
        ...,
    ]:
        return tuple(
            source
            for source
            in self.list_all()
            if (
                source.registered
                and (
                    source
                    .commercial_use_allowed
                    is True
                )
            )
        )

    @staticmethod
    def _normalize_id(
        source_id: str,
    ) -> str:
        if not isinstance(
            source_id,
            str,
        ):
            raise TypeError(
                "source_id must be a string."
            )

        normalized = (
            source_id
            .strip()
            .casefold()
        )

        if not normalized:
            raise ValueError(
                "source_id cannot be empty."
            )

        return normalized
