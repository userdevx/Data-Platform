from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import (
    parse_qs,
    urlparse,
)
from uuid import uuid4

import pytest

from engine.market_intelligence.normalization import (
    normalize_public_content,
)
from engine.market_intelligence.sources.census import (
    CensusSource,
)


class FakeResponse:
    def __init__(
        self,
        payload: object,
    ) -> None:
        self._body = json.dumps(
            payload
        ).encode(
            "utf-8"
        )

    def __enter__(
        self,
    ) -> "FakeResponse":
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:
        return False

    def read(
        self,
        size: int = -1,
    ) -> bytes:
        if size < 0:
            return self._body

        return self._body[
            :size
        ]


def test_census_source_converts_provider_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "CENSUS_API_KEY",
        raising=False,
    )

    credential = (
        "credential-"
        + uuid4().hex
    )

    env_path = (
        tmp_path
        / ".env"
    )

    env_path.write_text(
        (
            "CENSUS_API_KEY="
            f"{credential}\n"
        ),
        encoding="utf-8",
    )

    requested_fields = (
        "FIELD_A",
        "FIELD_B",
    )

    geography_field = (
        "geography_code"
    )

    provider_payload = [
        [
            *requested_fields,
            geography_field,
        ],
        [
            "value_a",
            "value_b",
            "1",
        ],
    ]

    captured: dict[
        str,
        object,
    ] = {}

    def opener(
        request,
        *,
        timeout: float,
    ) -> FakeResponse:
        captured[
            "url"
        ] = request.full_url

        captured[
            "timeout"
        ] = timeout

        return FakeResponse(
            provider_payload
        )

    source = CensusSource(
        dataset_path=(
            "/".join(
                (
                    "vintage",
                    "dataset",
                )
            )
        ),
        geography=(
            "geography:*"
        ),
        api_base_url=(
            "https://unit-test.invalid/data"
        ),
        env_path=env_path,
        opener=opener,
    )

    records = source.search(
        ",".join(
            requested_fields
        ),
        limit=1,
    )

    assert len(records) == 1

    record = records[0]

    assert (
        record.source_name
        == "U.S. Census Bureau"
    )

    assert (
        record.source_type
        == "official_statistics"
    )

    normalized = (
        normalize_public_content(
            record
        )
    )

    assert normalized is record

    structured = json.loads(
        record.retrieved_text
    )

    assert structured == {
        "FIELD_A": "value_a",
        "FIELD_B": "value_b",
        geography_field: "1",
    }

    request_url = str(
        captured["url"]
    )

    request_parameters = (
        parse_qs(
            urlparse(
                request_url
            ).query
        )
    )

    assert (
        request_parameters[
            "key"
        ][0]
        == credential
    )

    assert (
        credential
        not in record.source_url
    )

    assert (
        credential
        not in record.retrieved_text
    )

    assert (
        credential
        not in json.dumps(
            record.metadata
        )
    )

    safe_parameters = (
        parse_qs(
            urlparse(
                record.source_url
            ).query
        )
    )

    assert (
        "key"
        not in safe_parameters
    )


def test_census_source_applies_result_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "CENSUS_API_KEY",
        raising=False,
    )

    credential = (
        "credential-"
        + uuid4().hex
    )

    env_path = (
        tmp_path
        / ".env"
    )

    env_path.write_text(
        (
            "CENSUS_API_KEY="
            f"{credential}\n"
        ),
        encoding="utf-8",
    )

    field_name = (
        "FIELD_A"
    )

    provider_payload = [
        [
            field_name,
            "geography_code",
        ],
        [
            "value_1",
            "1",
        ],
        [
            "value_2",
            "2",
        ],
        [
            "value_3",
            "3",
        ],
    ]

    def opener(
        request,
        *,
        timeout: float,
    ) -> FakeResponse:
        return FakeResponse(
            provider_payload
        )

    source = CensusSource(
        dataset_path=(
            "vintage/dataset"
        ),
        geography=(
            "geography:*"
        ),
        api_base_url=(
            "https://unit-test.invalid/data"
        ),
        env_path=env_path,
        opener=opener,
    )

    records = source.search(
        field_name,
        limit=2,
    )

    assert len(records) == 2


def test_census_source_requires_credential(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "CENSUS_API_KEY",
        raising=False,
    )

    source = CensusSource(
        dataset_path=(
            "vintage/dataset"
        ),
        geography=(
            "geography:*"
        ),
        api_base_url=(
            "https://unit-test.invalid/data"
        ),
        env_path=(
            tmp_path
            / ".env"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="credential",
    ):
        source.search(
            "FIELD_A"
        )


def test_census_source_rejects_invalid_provider_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "CENSUS_API_KEY",
        raising=False,
    )

    credential = (
        "credential-"
        + uuid4().hex
    )

    env_path = (
        tmp_path
        / ".env"
    )

    env_path.write_text(
        (
            "CENSUS_API_KEY="
            f"{credential}\n"
        ),
        encoding="utf-8",
    )

    def opener(
        request,
        *,
        timeout: float,
    ) -> FakeResponse:
        return FakeResponse(
            {
                "unexpected": True,
            }
        )

    source = CensusSource(
        dataset_path=(
            "vintage/dataset"
        ),
        geography=(
            "geography:*"
        ),
        api_base_url=(
            "https://unit-test.invalid/data"
        ),
        env_path=env_path,
        opener=opener,
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected response type",
    ):
        source.search(
            "FIELD_A"
        )
