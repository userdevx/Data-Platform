from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from engine.market_intelligence.sources.models import (
    InformationSource,
)
from engine.market_intelligence.sources.registry import (
    InformationSourceRegistry,
)


def runtime_value(
    prefix: str,
) -> str:
    return (
        f"{prefix}-"
        f"{uuid4().hex}"
    )


def create_source(
    *,
    source_id: str | None = None,
    registered: bool = True,
    enabled: bool = True,
    collector_implemented: bool = False,
    ingestion_enabled: bool = False,
    commercial_use_allowed: bool | None = None,
    model_training_allowed: bool | None = None,
) -> InformationSource:
    actual_source_id = (
        source_id
        if source_id is not None
        else runtime_value(
            "source"
        )
    )

    return InformationSource(
        source_id=(
            actual_source_id
        ),
        name=runtime_value(
            "name"
        ),
        source_type=runtime_value(
            "type"
        ),
        authority=runtime_value(
            "authority"
        ),
        domains=(
            runtime_value(
                "domain"
            ),
        ),
        registered=registered,
        enabled=enabled,
        collector_implemented=(
            collector_implemented
        ),
        ingestion_enabled=(
            ingestion_enabled
        ),
        cost_free=None,
        authentication_required=None,
        api_available=None,
        stream_available=None,
        bulk_download_available=None,
        raw_storage_allowed=None,
        commercial_use_allowed=(
            commercial_use_allowed
        ),
        raw_redistribution_allowed=None,
        derived_analysis_allowed=None,
        model_training_allowed=(
            model_training_allowed
        ),
        attribution_required=None,
        share_alike_required=None,
        license_name=None,
        source_url=runtime_value(
            "source-reference"
        ),
        documentation_url=runtime_value(
            "documentation-reference"
        ),
    )


def test_information_source_accepts_unknown_policy():
    source = create_source()

    assert (
        source.raw_storage_allowed
        is None
    )

    assert (
        source.model_training_allowed
        is None
    )


def test_strict_boolean_rejects_integer():
    source = create_source()

    with pytest.raises(
        TypeError
    ):
        replace(
            source,
            registered=1,
        )


def test_optional_boolean_rejects_integer():
    source = create_source()

    with pytest.raises(
        TypeError
    ):
        replace(
            source,
            model_training_allowed=1,
        )


def test_domains_cannot_be_empty():
    source = create_source()

    with pytest.raises(
        ValueError
    ):
        replace(
            source,
            domains=(),
        )


def test_registry_lookup():
    source = create_source()

    registry = (
        InformationSourceRegistry(
            (
                source,
            )
        )
    )

    assert registry.has(
        source.source_id
    )

    assert (
        registry.get(
            source.source_id
        )
        is source
    )


def test_lookup_is_case_insensitive():
    source = create_source()

    registry = (
        InformationSourceRegistry(
            (
                source,
            )
        )
    )

    assert (
        registry.get(
            source.source_id.upper()
        )
        is source
    )


def test_unknown_source_fails():
    registry = (
        InformationSourceRegistry()
    )

    with pytest.raises(
        LookupError
    ):
        registry.get(
            runtime_value(
                "unknown-source"
            )
        )


def test_duplicate_source_id_fails():
    source_id = runtime_value(
        "source"
    )

    first = create_source(
        source_id=source_id
    )

    second = create_source(
        source_id=(
            source_id.upper()
        )
    )

    with pytest.raises(
        ValueError
    ):
        InformationSourceRegistry(
            (
                first,
                second,
            )
        )


def test_enabled_listing():
    enabled = create_source(
        enabled=True
    )

    disabled = create_source(
        enabled=False
    )

    registry = (
        InformationSourceRegistry(
            (
                disabled,
                enabled,
            )
        )
    )

    assert (
        registry.list_enabled()
        == (
            enabled,
        )
    )


def test_collection_state_is_independent_from_registration():
    registered_only = (
        create_source(
            registered=True,
            enabled=True,
            collector_implemented=False,
            ingestion_enabled=False,
        )
    )

    collectible = (
        create_source(
            registered=True,
            enabled=True,
            collector_implemented=True,
            ingestion_enabled=True,
        )
    )

    registry = (
        InformationSourceRegistry(
            (
                registered_only,
                collectible,
            )
        )
    )

    assert (
        registered_only
        in registry.list_enabled()
    )

    assert (
        registered_only
        not in registry.list_collectible()
    )

    assert (
        registry.list_collectible()
        == (
            collectible,
        )
    )


def test_training_policy_fails_closed():
    allowed = create_source(
        model_training_allowed=True
    )

    denied = create_source(
        model_training_allowed=False
    )

    unknown = create_source(
        model_training_allowed=None
    )

    registry = (
        InformationSourceRegistry(
            (
                unknown,
                denied,
                allowed,
            )
        )
    )

    training_sources = (
        registry
        .list_training_eligible()
    )

    assert allowed in training_sources

    assert denied not in training_sources

    assert unknown not in training_sources


def test_commercial_policy_fails_closed():
    allowed = create_source(
        commercial_use_allowed=True
    )

    denied = create_source(
        commercial_use_allowed=False
    )

    unknown = create_source(
        commercial_use_allowed=None
    )

    registry = (
        InformationSourceRegistry(
            (
                unknown,
                denied,
                allowed,
            )
        )
    )

    commercial_sources = (
        registry
        .list_commercially_usable()
    )

    assert allowed in commercial_sources

    assert denied not in commercial_sources

    assert unknown not in commercial_sources
