from __future__ import annotations

from typing import Any

from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.realtime.models import (
    RealTimeObservation,
)
from engine.realtime.source import (
    RealTimeSource,
)


class RealTimeIngestionService:
    """
    Persist real observations through the existing
    Data Engine write path.

    Acquisition remains the responsibility of a
    RealTimeSource. This service owns only the
    observation-to-Data-Engine persistence boundary.
    """

    def __init__(
        self,
        *,
        writer: DataEngineRecordWriter | None = None,
    ) -> None:
        self.writer = (
            writer
            if writer is not None
            else DataEngineRecordWriter()
        )

    def ingest(
        self,
        observation: RealTimeObservation,
    ) -> Any:
        if not isinstance(
            observation,
            RealTimeObservation,
        ):
            raise TypeError(
                "observation must be a "
                "RealTimeObservation."
            )

        metadata = dict(
            observation.metadata
        )

        metadata[
            "observation_id"
        ] = observation.observation_id

        metadata[
            "observed_at"
        ] = observation.observed_at

        return self.writer.write(
            source=observation.source,
            category=observation.category,
            data_type=observation.data_type,
            value=observation.value,
            unit=observation.unit,
            metadata=metadata,
        )

    def ingest_source(
        self,
        source: RealTimeSource,
    ) -> Any:
        if not isinstance(
            source,
            RealTimeSource,
        ):
            raise TypeError(
                "source must implement "
                "RealTimeSource."
            )

        observation = source.collect()

        return self.ingest(
            observation
        )
