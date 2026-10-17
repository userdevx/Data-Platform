from __future__ import annotations

import pytest

from engine.market_intelligence.sources.catalog import (
    INFORMATION_SOURCES,
)
from engine.market_intelligence.sources.census import (
    CensusSource,
)
from engine.market_intelligence.sources.registry import (
    InformationSourceRegistry,
)
from engine.market_intelligence.sources.runtime import (
    SourceRuntimeConfiguration,
    build_public_source_registry,
)


def test_builds_census_executable_registry() -> None:
    configuration = (
        SourceRuntimeConfiguration(
            source_id="census",
            options={
                "dataset_path": (
                    "runtime/dataset"
                ),
                "geography": (
                    "region:*"
                ),
            },
        ),
    )

    registry = (
        build_public_source_registry(
            configuration
        )
    )

    assert (
        len(
            registry.all()
        )
        == 1
    )

    assert registry.has(
        "U.S. Census Bureau"
    )

    source = registry.get(
        "U.S. Census Bureau"
    )

    assert isinstance(
        source,
        CensusSource,
    )

    assert (
        source.dataset_path
        == "runtime/dataset"
    )

    assert (
        source.geography
        == "region:*"
    )


def test_runtime_configuration_normalizes_source_id() -> None:
    configuration = (
        SourceRuntimeConfiguration(
            source_id="  CENSUS  ",
            options={
                "dataset_path": (
                    "runtime/dataset"
                ),
                "geography": (
                    "region:*"
                ),
            },
        )
    )

    assert (
        configuration.source_id
        == "census"
    )


def test_runtime_rejects_duplicate_source() -> None:
    configuration = (
        SourceRuntimeConfiguration(
            source_id="census",
            options={
                "dataset_path": (
                    "runtime/dataset"
                ),
                "geography": (
                    "region:*"
                ),
            },
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Duplicate runtime source "
            "configuration"
        ),
    ):
        build_public_source_registry(
            (
                configuration,
                configuration,
            )
        )


def test_runtime_rejects_missing_census_options() -> None:
    configuration = (
        SourceRuntimeConfiguration(
            source_id="census",
            options={},
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Missing Census runtime options"
        ),
    ):
        build_public_source_registry(
            configuration
        )


def test_runtime_rejects_unknown_census_options() -> None:
    configuration = (
        SourceRuntimeConfiguration(
            source_id="census",
            options={
                "dataset_path": (
                    "runtime/dataset"
                ),
                "geography": (
                    "region:*"
                ),
                "unsupported_option": True,
            },
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported Census runtime options"
        ),
    ):
        build_public_source_registry(
            configuration
        )


def test_runtime_blocks_source_not_enabled_for_ingestion() -> None:
    information_registry = (
        InformationSourceRegistry(
            INFORMATION_SOURCES
        )
    )

    disabled_sources = tuple(
        source
        for source
        in information_registry.list_all()
        if (
            source.source_id
            != "census"
            and not (
                source.collector_implemented
                and source.ingestion_enabled
            )
        )
    )

    assert disabled_sources

    disabled_source = (
        disabled_sources[0]
    )

    configuration = (
        SourceRuntimeConfiguration(
            source_id=(
                disabled_source.source_id
            ),
            options={},
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "not enabled for runtime ingestion"
        ),
    ):
        build_public_source_registry(
            configuration,
            information_registry=(
                information_registry
            ),
        )


def test_runtime_build_does_not_require_api_key() -> None:
    configuration = (
        SourceRuntimeConfiguration(
            source_id="census",
            options={
                "dataset_path": (
                    "runtime/dataset"
                ),
                "geography": (
                    "region:*"
                ),
            },
        ),
    )

    registry = (
        build_public_source_registry(
            configuration
        )
    )

    source = registry.get(
        "U.S. Census Bureau"
    )

    assert isinstance(
        source,
        CensusSource,
    )
