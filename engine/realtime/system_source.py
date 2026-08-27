from __future__ import annotations

from typing import Any

from engine.realtime.models import (
    RealTimeObservation,
    SystemSnapshot,
    utc_now,
)
from engine.realtime.source import (
    RealTimeSource,
)
from engine.system.system_readers import (
    read_cpu,
    read_disk,
    read_memory,
    read_uptime,
)


_REQUIRED_READER_FIELDS = {
    "source",
    "category",
    "sensor_type",
    "value",
    "unit",
    "created_at",
}


class SystemRuntimeSource(
    RealTimeSource
):
    """
    Collect one truthful runtime snapshot from the
    existing operating-system readers.

    This source performs acquisition only.
    It does not write directly to the Data Engine.
    """

    def collect(
        self,
    ) -> RealTimeObservation:
        collection_started_at = (
            utc_now()
        )

        cpu = self._require_reader_record(
            read_cpu(),
            "cpu",
        )

        memory = self._require_reader_record(
            read_memory(),
            "memory",
        )

        disk = self._require_reader_record(
            read_disk(),
            "disk",
        )

        uptime = self._require_reader_record(
            read_uptime(),
            "uptime",
        )

        collection_completed_at = (
            utc_now()
        )

        snapshot = SystemSnapshot(
            cpu=cpu,
            memory=memory,
            disk=disk,
            uptime=uptime,
        )

        return RealTimeObservation(
            source="system_runtime",
            category="runtime_observation",
            data_type="runtime_metric",
            sensor_type="system_snapshot",
            value=snapshot.to_dict(),
            unit="snapshot",
            observed_at=(
                collection_completed_at
            ),
            metadata={
                "source_reference": (
                    "engine.system.system_readers"
                ),
                "collector": (
                    type(self).__name__
                ),
                "collection_started_at": (
                    collection_started_at
                ),
                "collection_completed_at": (
                    collection_completed_at
                ),
                "acquisition_mode": (
                    "local_operating_system"
                ),
            },
        )

    @staticmethod
    def _require_reader_record(
        value: Any,
        reader_name: str,
    ) -> dict[str, Any]:
        if not isinstance(
            value,
            dict,
        ):
            raise TypeError(
                f"{reader_name} reader returned "
                f"{type(value).__name__}; "
                "expected dict."
            )

        missing_fields = (
            _REQUIRED_READER_FIELDS
            - value.keys()
        )

        if missing_fields:
            raise ValueError(
                f"{reader_name} reader is missing "
                f"fields: "
                f"{sorted(missing_fields)}"
            )

        return dict(
            value
        )
