from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

from engine.market_intelligence.models import (
    PublicContentRecord,
)
from engine.market_intelligence.sources.base import (
    PublicSource,
)


class CensusSource(PublicSource):
    """
    U.S. Census Bureau Data API adapter.

    The PublicSource.search() contract requires a string.
    For Census, that runtime string represents the Census
    variables requested through the API's `get` parameter.

    Dataset and geography are runtime configuration rather
    than hardcoded research assumptions.

    API credentials are read from the process environment
    first and then from the configured environment file.

    The credential is never stored in PublicContentRecord,
    metadata, retrieved_text, or source_url.
    """

    SOURCE_NAME = "U.S. Census Bureau"
    SOURCE_TYPE = "official_statistics"

    def __init__(
        self,
        *,
        dataset_path: str,
        geography: str,
        api_base_url: str = (
            "https://api.census.gov/data"
        ),
        api_key_environment_name: str = (
            "CENSUS_API_KEY"
        ),
        env_path: str | Path = ".env",
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 2_000_000,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.dataset_path = (
            self._normalize_dataset_path(
                dataset_path
            )
        )

        self.geography = (
            self._require_text(
                geography,
                "geography",
            )
        )

        self.api_base_url = (
            self._normalize_api_base_url(
                api_base_url
            )
        )

        self.api_key_environment_name = (
            self._require_text(
                api_key_environment_name,
                "api_key_environment_name",
            )
        )

        self.env_path = Path(
            env_path
        )

        if (
            not isinstance(
                timeout_seconds,
                (int, float),
            )
            or isinstance(
                timeout_seconds,
                bool,
            )
        ):
            raise TypeError(
                "timeout_seconds must be numeric."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater "
                "than zero."
            )

        if (
            not isinstance(
                max_response_bytes,
                int,
            )
            or isinstance(
                max_response_bytes,
                bool,
            )
        ):
            raise TypeError(
                "max_response_bytes must be "
                "an integer."
            )

        if max_response_bytes < 1:
            raise ValueError(
                "max_response_bytes must be "
                "greater than zero."
            )

        self.timeout_seconds = float(
            timeout_seconds
        )

        self.max_response_bytes = (
            max_response_bytes
        )

        self._opener = (
            opener
            if opener is not None
            else urllib.request.urlopen
        )

    @property
    def source_name(
        self,
    ) -> str:
        return self.SOURCE_NAME

    @property
    def source_type(
        self,
    ) -> str:
        return self.SOURCE_TYPE

    def search(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> list[PublicContentRecord]:
        fields = self._parse_fields(
            query
        )

        normalized_limit = (
            self._validate_limit(
                limit
            )
        )

        api_key = self._read_api_key()

        request_url = (
            self._build_request_url(
                fields=fields,
                api_key=api_key,
            )
        )

        safe_source_url = (
            self._build_safe_source_url(
                fields=fields
            )
        )

        request = urllib.request.Request(
            request_url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Data-Platform/"
                    "Market-Intelligence"
                ),
            },
            method="GET",
        )

        try:
            with self._opener(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = response.read(
                    self.max_response_bytes
                    + 1
                )

        except urllib.error.HTTPError as error:
            raise RuntimeError(
                "Census API returned HTTP "
                f"{error.code}."
            ) from error

        except urllib.error.URLError as error:
            raise RuntimeError(
                "Census API network request "
                "failed."
            ) from error

        if (
            len(body)
            > self.max_response_bytes
        ):
            raise RuntimeError(
                "Census API response exceeded "
                "the configured response limit."
            )

        payload = (
            self._decode_payload(
                body
            )
        )

        return self._records_from_payload(
            payload=payload,
            requested_fields=fields,
            safe_source_url=(
                safe_source_url
            ),
            limit=normalized_limit,
        )

    def _records_from_payload(
        self,
        *,
        payload: list[Any],
        requested_fields: tuple[
            str,
            ...,
        ],
        safe_source_url: str,
        limit: int,
    ) -> list[PublicContentRecord]:
        if not payload:
            raise RuntimeError(
                "Census API returned an "
                "empty response."
            )

        header = payload[0]

        if not isinstance(
            header,
            list,
        ):
            raise RuntimeError(
                "Census API header is invalid."
            )

        if not header:
            raise RuntimeError(
                "Census API header is empty."
            )

        response_fields = tuple(
            self._require_text(
                str(field),
                "response field",
            )
            for field in header
        )

        records: list[
            PublicContentRecord
        ] = []

        for row_number, row in enumerate(
            payload[1:],
            start=1,
        ):
            if len(records) >= limit:
                break

            if not isinstance(
                row,
                list,
            ):
                raise RuntimeError(
                    "Census API returned an "
                    "invalid information row."
                )

            if len(row) != len(
                response_fields
            ):
                raise RuntimeError(
                    "Census API row does not "
                    "match the response header."
                )

            structured_row = {
                field: value
                for field, value
                in zip(
                    response_fields,
                    row,
                    strict=True,
                )
            }

            retrieved_text = json.dumps(
                structured_row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(
                    ",",
                    ":",
                ),
            )

            records.append(
                PublicContentRecord.create(
                    source_name=(
                        self.source_name
                    ),
                    source_type=(
                        self.source_type
                    ),
                    retrieved_text=(
                        retrieved_text
                    ),
                    source_url=(
                        safe_source_url
                    ),
                    metadata={
                        "dataset_path": (
                            self.dataset_path
                        ),
                        "geography": (
                            self.geography
                        ),
                        "requested_fields": list(
                            requested_fields
                        ),
                        "response_fields": list(
                            response_fields
                        ),
                        "row_number": (
                            row_number
                        ),
                    },
                )
            )

        return records

    def _build_request_url(
        self,
        *,
        fields: tuple[
            str,
            ...,
        ],
        api_key: str,
    ) -> str:
        parameters = {
            "get": ",".join(
                fields
            ),
            "for": self.geography,
            "key": api_key,
        }

        return (
            self._dataset_url()
            + "?"
            + urllib.parse.urlencode(
                parameters
            )
        )

    def _build_safe_source_url(
        self,
        *,
        fields: tuple[
            str,
            ...,
        ],
    ) -> str:
        parameters = {
            "get": ",".join(
                fields
            ),
            "for": self.geography,
        }

        return (
            self._dataset_url()
            + "?"
            + urllib.parse.urlencode(
                parameters
            )
        )

    def _dataset_url(
        self,
    ) -> str:
        return (
            f"{self.api_base_url}/"
            f"{self.dataset_path}"
        )

    def _read_api_key(
        self,
    ) -> str:
        process_value = (
            os.environ
            .get(
                self.api_key_environment_name,
                "",
            )
            .strip()
        )

        if process_value:
            return process_value

        if not self.env_path.exists():
            raise RuntimeError(
                "Census API credential "
                "is not configured."
            )

        prefix = (
            f"{self.api_key_environment_name}="
        )

        for raw_line in (
            self.env_path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
        ):
            line = raw_line.strip()

            if (
                not line
                or line.startswith("#")
            ):
                continue

            if not line.startswith(
                prefix
            ):
                continue

            value = (
                line[
                    len(prefix):
                ]
                .strip()
                .strip('"')
                .strip("'")
            )

            if value:
                return value

        raise RuntimeError(
            "Census API credential "
            "is not configured."
        )

    @staticmethod
    def _decode_payload(
        body: bytes,
    ) -> list[Any]:
        try:
            payload = json.loads(
                body.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise RuntimeError(
                "Census API did not return "
                "valid JSON."
            ) from error

        if not isinstance(
            payload,
            list,
        ):
            raise RuntimeError(
                "Census API returned an "
                "unexpected response type."
            )

        return payload

    @staticmethod
    def _parse_fields(
        query: str,
    ) -> tuple[
        str,
        ...,
    ]:
        normalized_query = (
            CensusSource._require_text(
                query,
                "query",
            )
        )

        fields: list[str] = []
        seen: set[str] = set()

        for raw_field in (
            normalized_query.split(",")
        ):
            field = raw_field.strip()

            if not field:
                continue

            if field in seen:
                continue

            seen.add(
                field
            )

            fields.append(
                field
            )

        if not fields:
            raise ValueError(
                "At least one Census field "
                "must be requested."
            )

        return tuple(
            fields
        )

    @staticmethod
    def _validate_limit(
        limit: int,
    ) -> int:
        if (
            not isinstance(
                limit,
                int,
            )
            or isinstance(
                limit,
                bool,
            )
        ):
            raise TypeError(
                "limit must be an integer."
            )

        if limit < 1:
            raise ValueError(
                "limit must be greater "
                "than zero."
            )

        return limit

    @staticmethod
    def _normalize_dataset_path(
        value: str,
    ) -> str:
        normalized = (
            CensusSource._require_text(
                value,
                "dataset_path",
            )
            .strip("/")
        )

        if (
            "://" in normalized
            or "?" in normalized
            or "#" in normalized
        ):
            raise ValueError(
                "dataset_path must be a "
                "Census API dataset path."
            )

        return normalized

    @staticmethod
    def _normalize_api_base_url(
        value: str,
    ) -> str:
        normalized = (
            CensusSource._require_text(
                value,
                "api_base_url",
            )
            .rstrip("/")
        )

        if not normalized.startswith(
            "https://"
        ):
            raise ValueError(
                "api_base_url must use HTTPS."
            )

        return normalized

    @staticmethod
    def _require_text(
        value: str,
        field_name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be "
                "a string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot "
                "be empty."
            )

        return normalized
