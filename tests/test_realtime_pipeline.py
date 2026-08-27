from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from inspect import isabstract
from multiprocessing import Process
from pathlib import Path
from typing import Any

from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.query import QueryService
from engine.realtime.ingestion import (
    RealTimeIngestionService,
)
from engine.realtime.models import (
    RealTimeObservation,
    SystemSnapshot,
)
from engine.realtime.query import (
    RealTimeQueryService,
)
from engine.realtime.source import (
    RealTimeSource,
)
from engine.realtime.system_source import (
    SystemRuntimeSource,
)
from engine.realtime.worker import (
    RealTimeCollectionWorker,
)
from engine.storage.json_backend import (
    LocalJsonStorageBackend,
)


def build_query_service(
    data_file: Path,
) -> QueryService:
    backend = LocalJsonStorageBackend(
        str(data_file)
    )

    return QueryService(
        backend
    )


def build_observation(
    *,
    observed_at: str | None = None,
    sequence: int = 1,
    source: str = "test_runtime_source",
) -> RealTimeObservation:
    return RealTimeObservation(
        source=source,
        category="runtime_observation",
        data_type="runtime_metric",
        sensor_type="system_snapshot",
        value={
            "sequence": sequence,
        },
        unit="snapshot",
        observed_at=(
            observed_at
            if observed_at is not None
            else datetime.now(
                timezone.utc
            ).isoformat()
        ),
        metadata={
            "acquisition_mode": (
                "test_fixture"
            ),
        },
    )


class GeneratedRealTimeSource(
    RealTimeSource
):
    def __init__(
        self,
    ) -> None:
        self.collection_count = 0

    def collect(
        self,
    ) -> RealTimeObservation:
        self.collection_count += 1

        return build_observation(
            sequence=self.collection_count
        )


def process_writer(
    data_file: str,
    sequence: int,
) -> None:
    query_service = build_query_service(
        Path(
            data_file
        )
    )

    writer = DataEngineRecordWriter(
        query_service=query_service,
        max_id_retries=10,
    )

    writer.write(
        source="test_runtime_source",
        category="runtime_observation",
        data_type="runtime_metric",
        sensor_type="system_snapshot",
        value={
            "sequence": sequence,
        },
        unit="snapshot",
        metadata={
            "process_sequence": sequence,
        },
    )


def test_realtime_source_contract_is_abstract() -> None:
    assert isabstract(
        RealTimeSource
    )

    assert getattr(
        RealTimeSource.collect,
        "__isabstractmethod__",
        False,
    )


def test_system_snapshot_serialization() -> None:
    snapshot = SystemSnapshot(
        cpu={
            "value": 1,
        },
        memory={
            "value": 2,
        },
        disk={
            "value": 3,
        },
        uptime={
            "value": 4,
        },
    )

    serialized = snapshot.to_dict()

    assert set(
        serialized
    ) == {
        "cpu",
        "memory",
        "disk",
        "uptime",
    }


def test_system_runtime_source_reads_real_system() -> None:
    observation = (
        SystemRuntimeSource()
        .collect()
    )

    assert (
        observation.source
        == "system_runtime"
    )

    assert (
        observation.data_type
        == "runtime_metric"
    )

    assert (
        observation.sensor_type
        == "system_snapshot"
    )

    assert (
        observation.unit
        == "snapshot"
    )

    assert set(
        observation.value
    ) == {
        "cpu",
        "memory",
        "disk",
        "uptime",
    }

    for reader_name in (
        "cpu",
        "memory",
        "disk",
        "uptime",
    ):
        reader_record = (
            observation.value[
                reader_name
            ]
        )

        assert isinstance(
            reader_record,
            dict,
        )

        assert {
            "source",
            "category",
            "sensor_type",
            "value",
            "unit",
            "created_at",
        }.issubset(
            reader_record
        )


def test_writer_preserves_legacy_records(
    tmp_path: Path,
) -> None:
    data_file = (
        tmp_path
        / "records.json"
    )

    backend = LocalJsonStorageBackend(
        str(
            data_file
        )
    )

    legacy_records: list[dict[str, Any]] = [
        {
            "source": "legacy_fixture",
            "value": {
                "sequence": 1,
            },
        },
        {
            "id": "legacy-string-id",
            "source": "legacy_fixture",
            "value": {
                "sequence": 2,
            },
        },
    ]

    backend.save_records(
        legacy_records
    )

    query_service = QueryService(
        backend
    )

    writer = DataEngineRecordWriter(
        query_service=query_service
    )

    stored = writer.write(
        source="test_runtime_source",
        category="runtime_observation",
        data_type="runtime_metric",
        sensor_type="system_snapshot",
        value={
            "sequence": 3,
        },
        unit="snapshot",
    )

    records = (
        backend.get_all_records()
    )

    assert len(
        records
    ) == 3

    assert (
        records[0]
        == legacy_records[0]
    )

    assert (
        records[1]
        == legacy_records[1]
    )

    assert isinstance(
        stored["id"],
        int,
    )


def test_ingestion_persists_observation(
    tmp_path: Path,
) -> None:
    query_service = build_query_service(
        tmp_path
        / "records.json"
    )

    writer = DataEngineRecordWriter(
        query_service=query_service
    )

    ingestion = RealTimeIngestionService(
        writer=writer
    )

    observation = build_observation()

    stored = ingestion.ingest(
        observation
    )

    records = (
        query_service
        .get_all_records()
    )

    assert len(
        records
    ) == 1

    assert (
        stored["data_type"]
        == "runtime_metric"
    )

    assert (
        stored["sensor_type"]
        == "system_snapshot"
    )

    assert (
        stored["metadata"][
            "observation_id"
        ]
        == observation.observation_id
    )

    assert (
        stored["metadata"][
            "observed_at"
        ]
        == observation.observed_at
    )


def test_historical_query_orders_and_bounds_records(
    tmp_path: Path,
) -> None:
    query_service = build_query_service(
        tmp_path
        / "records.json"
    )

    writer = DataEngineRecordWriter(
        query_service=query_service
    )

    ingestion = RealTimeIngestionService(
        writer=writer
    )

    now = datetime.now(
        timezone.utc
    )

    earlier = (
        now
        - timedelta(
            minutes=1
        )
    )

    earlier_observation = (
        build_observation(
            observed_at=(
                earlier.isoformat()
            ),
            sequence=1,
            source="system_runtime",
        )
    )

    newer_observation = (
        build_observation(
            observed_at=(
                now.isoformat()
            ),
            sequence=2,
            source="system_runtime",
        )
    )

    ingestion.ingest(
        earlier_observation
    )

    ingestion.ingest(
        newer_observation
    )

    query = RealTimeQueryService(
        query_service=query_service
    )

    history = (
        query.system_snapshot_history(
            limit=10
        )
    )

    assert len(
        history
    ) == 2

    assert (
        history[0][
            "metadata"
        ][
            "observation_id"
        ]
        == newer_observation.observation_id
    )

    latest = (
        query.latest_system_snapshot()
    )

    assert latest is not None

    assert (
        latest[
            "metadata"
        ][
            "observation_id"
        ]
        == newer_observation.observation_id
    )

    bounded = (
        query.system_snapshot_history(
            limit=10,
            start_at=now.isoformat(),
            end_at=now.isoformat(),
        )
    )

    assert len(
        bounded
    ) == 1

    assert (
        bounded[0][
            "metadata"
        ][
            "observation_id"
        ]
        == newer_observation.observation_id
    )


def test_bounded_worker_persists_requested_iterations(
    tmp_path: Path,
) -> None:
    query_service = build_query_service(
        tmp_path
        / "records.json"
    )

    writer = DataEngineRecordWriter(
        query_service=query_service
    )

    ingestion = RealTimeIngestionService(
        writer=writer
    )

    source = GeneratedRealTimeSource()

    worker = RealTimeCollectionWorker(
        source=source,
        ingestion_service=ingestion,
        interval_seconds=0,
        max_consecutive_failures=5,
    )

    iteration_count = 3

    result = worker.run(
        iterations=iteration_count
    )

    records = (
        query_service
        .get_all_records()
    )

    assert (
        result["attempts"]
        == iteration_count
    )

    assert (
        result["successes"]
        == iteration_count
    )

    assert (
        result["failures"]
        == 0
    )

    assert len(
        records
    ) == iteration_count


def test_multiple_process_writers_preserve_all_records(
    tmp_path: Path,
) -> None:
    data_file = (
        tmp_path
        / "records.json"
    )

    LocalJsonStorageBackend(
        str(
            data_file
        )
    )

    process_count = 4

    processes = [
        Process(
            target=process_writer,
            args=(
                str(
                    data_file
                ),
                sequence,
            ),
        )
        for sequence in range(
            1,
            process_count + 1,
        )
    ]

    for process in processes:
        process.start()

    for process in processes:
        process.join(
            timeout=30
        )

    exit_codes = [
        process.exitcode
        for process in processes
    ]

    assert exit_codes == [
        0
    ] * process_count

    backend = LocalJsonStorageBackend(
        str(
            data_file
        )
    )

    records = (
        backend.get_all_records()
    )

    assert len(
        records
    ) == process_count

    ids = [
        record["id"]
        for record in records
    ]

    assert all(
        isinstance(
            record_id,
            int,
        )
        for record_id in ids
    )

    assert len(
        set(
            ids
        )
    ) == process_count

    sequences = sorted(
        record[
            "value"
        ][
            "sequence"
        ]
        for record in records
    )

    assert sequences == list(
        range(
            1,
            process_count + 1,
        )
    )
