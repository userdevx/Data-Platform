from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engine.backend import get_backend
from engine.query import QueryService


class RealTimeQueryService:
    """
    Read persisted real-time runtime observations from
    the existing Data Engine.

    This service does not create a separate query store.
    """

    def __init__(
        self,
        *,
        query_service: QueryService | None = None,
    ) -> None:
        self.query_service = (
            query_service
            if query_service is not None
            else QueryService(
                get_backend()
            )
        )

    def latest_system_snapshot(
        self,
    ) -> dict[str, Any] | None:
        history = self.system_snapshot_history(
            limit=1
        )

        if not history:
            return None

        return history[0]

    def system_snapshot_history(
        self,
        *,
        limit: int = 10,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            limit,
            int,
        ):
            raise TypeError(
                "limit must be an integer."
            )

        if limit < 1:
            raise ValueError(
                "limit must be at least 1."
            )

        start_time = self._parse_boundary(
            start_at,
            "start_at",
        )

        end_time = self._parse_boundary(
            end_at,
            "end_at",
        )

        if (
            start_time is not None
            and end_time is not None
            and start_time > end_time
        ):
            raise ValueError(
                "start_at cannot be later "
                "than end_at."
            )

        records = (
            self.query_service
            .get_all_records()
        )

        matches = []

        for record in records:
            if not self._is_system_snapshot(
                record
            ):
                continue

            observed_time = (
                self._record_time(
                    record
                )
            )

            if (
                start_time is not None
                and (
                    observed_time is None
                    or observed_time < start_time
                )
            ):
                continue

            if (
                end_time is not None
                and (
                    observed_time is None
                    or observed_time > end_time
                )
            ):
                continue

            matches.append(
                record
            )

        matches.sort(
            key=self._sort_key,
            reverse=True,
        )

        return matches[
            :limit
        ]

    @staticmethod
    def _is_system_snapshot(
        record: Any,
    ) -> bool:
        if not isinstance(
            record,
            dict,
        ):
            return False

        return (
            record.get(
                "source"
            )
            == "system_runtime"
            and record.get(
                "category"
            )
            == "runtime_observation"
            and record.get(
                "data_type"
            )
            == "runtime_metric"
            and record.get(
                "sensor_type"
            )
            == "system_snapshot"
        )

    @classmethod
    def _sort_key(
        cls,
        record: dict[str, Any],
    ) -> datetime:
        observed_time = (
            cls._record_time(
                record
            )
        )

        if observed_time is not None:
            return observed_time

        return datetime.min.replace(
            tzinfo=timezone.utc
        )

    @classmethod
    def _record_time(
        cls,
        record: dict[str, Any],
    ) -> datetime | None:
        metadata = record.get(
            "metadata"
        )

        if isinstance(
            metadata,
            dict,
        ):
            observed_at = metadata.get(
                "observed_at"
            )

            parsed = cls._parse_timestamp(
                observed_at
            )

            if parsed is not None:
                return parsed

        return cls._parse_timestamp(
            record.get(
                "created_at"
            )
        )

    @classmethod
    def _parse_boundary(
        cls,
        value: str | None,
        field_name: str,
    ) -> datetime | None:
        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be a "
                "timestamp string or None."
            )

        parsed = cls._parse_timestamp(
            value
        )

        if parsed is None:
            raise ValueError(
                f"{field_name} must be a "
                "valid ISO-8601 timestamp."
            )

        return parsed

    @staticmethod
    def _parse_timestamp(
        value: Any,
    ) -> datetime | None:
        if not isinstance(
            value,
            str,
        ):
            return None

        normalized = value.strip()

        if not normalized:
            return None

        if normalized.endswith(
            "Z"
        ):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                normalized
            )
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )
