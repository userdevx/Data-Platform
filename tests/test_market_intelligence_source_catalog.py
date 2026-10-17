from __future__ import annotations

from engine.market_intelligence.sources.catalog import (
    EXPECTED_INFORMATION_SOURCE_IDS,
    INFORMATION_SOURCES,
    build_information_source_registry,
)


CONNECTED_SOURCE_ID = "census"


def _get_catalog_source(
    source_id: str,
):
    matches = tuple(
        source
        for source in INFORMATION_SOURCES
        if source.source_id == source_id
    )

    assert len(matches) == 1

    return matches[0]


def _other_catalog_sources(
    source_id: str,
):
    return tuple(
        source
        for source in INFORMATION_SOURCES
        if source.source_id != source_id
    )


def test_catalog_contains_exact_expected_sources():
    actual_ids = {
        source.source_id
        for source in INFORMATION_SOURCES
    }

    assert actual_ids == (
        EXPECTED_INFORMATION_SOURCE_IDS
    )


def test_catalog_contains_twenty_four_sources():
    assert len(
        INFORMATION_SOURCES
    ) == 24


def test_all_catalog_sources_are_registered():
    assert all(
        source.registered
        for source in INFORMATION_SOURCES
    )


def test_all_catalog_sources_are_enabled():
    assert all(
        source.enabled
        for source in INFORMATION_SOURCES
    )


def test_only_proven_collector_is_implemented():
    census = _get_catalog_source(
        CONNECTED_SOURCE_ID
    )

    other_sources = (
        _other_catalog_sources(
            CONNECTED_SOURCE_ID
        )
    )

    assert (
        census.collector_implemented
        is True
    )

    assert all(
        source.collector_implemented
        is False
        for source in other_sources
    )


def test_only_proven_ingestion_is_enabled():
    census = _get_catalog_source(
        CONNECTED_SOURCE_ID
    )

    other_sources = (
        _other_catalog_sources(
            CONNECTED_SOURCE_ID
        )
    )

    assert (
        census.ingestion_enabled
        is True
    )

    assert all(
        source.ingestion_enabled
        is False
        for source in other_sources
    )


def test_connected_census_requires_authentication():
    census = _get_catalog_source(
        CONNECTED_SOURCE_ID
    )

    assert (
        census.authentication_required
        is True
    )

    assert census.api_available is True

    assert census.api_url


def test_unreviewed_training_rights_fail_closed():
    assert all(
        source.model_training_allowed
        is None
        for source in INFORMATION_SOURCES
    )


def test_unreviewed_commercial_rights_fail_closed():
    assert all(
        source.commercial_use_allowed
        is None
        for source in INFORMATION_SOURCES
    )


def test_every_source_has_domain_information():
    assert all(
        source.domains
        for source in INFORMATION_SOURCES
    )


def test_every_source_has_official_references():
    for source in INFORMATION_SOURCES:
        assert source.source_url.strip()

        assert (
            source
            .documentation_url
            .strip()
        )


def test_registry_contains_entire_catalog():
    registry = (
        build_information_source_registry()
    )

    assert len(
        registry.list_all()
    ) == 24

    for source_id in (
        EXPECTED_INFORMATION_SOURCE_IDS
    ):
        assert registry.has(
            source_id
        )


def test_only_proven_source_is_collectible():
    registry = (
        build_information_source_registry()
    )

    collectible = (
        registry.list_collectible()
    )

    assert len(
        collectible
    ) == 1

    assert (
        collectible[0].source_id
        == CONNECTED_SOURCE_ID
    )

    assert (
        collectible[0]
        .collector_implemented
        is True
    )

    assert (
        collectible[0]
        .ingestion_enabled
        is True
    )


def test_registered_does_not_mean_collectible():
    registry = (
        build_information_source_registry()
    )

    all_sources = (
        registry.list_all()
    )

    collectible_ids = {
        source.source_id
        for source in (
            registry.list_collectible()
        )
    }

    assert len(
        all_sources
    ) == 24

    assert (
        collectible_ids
        == {
            CONNECTED_SOURCE_ID
        }
    )

    assert all(
        source.source_id
        in collectible_ids
        or (
            source.collector_implemented
            is False
            and source.ingestion_enabled
            is False
        )
        for source in all_sources
    )


def test_no_source_is_training_eligible_before_policy_review():
    registry = (
        build_information_source_registry()
    )

    assert (
        registry
        .list_training_eligible()
        == ()
    )
