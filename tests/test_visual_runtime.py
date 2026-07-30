from datetime import UTC, datetime
from uuid import uuid4

from engine.intelligence.vision.config import (
    SamplingConfiguration,
    StorageConfiguration,
    ValidationConfiguration,
    VisualConfiguration,
)
from engine.intelligence.vision.models import (
    MediaFrame,
    VisualEntity,
    VisualObservation,
)
from engine.intelligence.vision.providers.unavailable import (
    UnavailableVisualAnalyzer,
)
from engine.intelligence.vision.runtime import (
    VisualRuntime,
)


def dynamic_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def configuration(
    *,
    enabled: bool,
) -> VisualConfiguration:
    return VisualConfiguration(
        enabled=enabled,
        provider=(
            dynamic_value("provider")
            if enabled
            else ""
        ),
        model=dynamic_value("model"),
        maximum_media_size_bytes=1024,
        sampling=SamplingConfiguration(
            minimum_interval_ms=1,
            maximum_interval_ms=1000,
            analyze_on_change=True,
            maximum_pending_frames=1,
        ),
        validation=ValidationConfiguration(
            minimum_entity_confidence=0.0,
            minimum_relation_confidence=0.0,
            minimum_temporal_frames=2,
        ),
        storage=StorageConfiguration(
            store_raw_frames=False,
            store_provider_responses=False,
            store_validated_observations=True,
        ),
    )


def frame() -> MediaFrame:
    return MediaFrame(
        frame_id=dynamic_value("frame"),
        source_id=dynamic_value("source"),
        sequence_id=dynamic_value("sequence"),
        frame_index=0,
        captured_at=datetime.now(UTC).isoformat(),
        media_location=dynamic_value("location"),
        media_type="image/test",
    )


class GeneratedAnalyzer:
    def analyze(self, *, request, frame):
        return VisualObservation(
            observation_id=dynamic_value("observation"),
            request_id=request.request_id,
            frame_id=frame.frame_id,
            sequence_id=frame.sequence_id,
            frame_index=frame.frame_index,
            captured_at=frame.captured_at,
            query=request.query,
            scene_description=dynamic_value(
                "description"
            ),
            entities=(
                VisualEntity(
                    entity_id=dynamic_value("entity"),
                    label=dynamic_value("label"),
                    confidence=0.92,
                ),
            ),
            relations=(),
            visible_text=(),
            uncertainty=(),
            provider_name=dynamic_value("provider"),
            provider_model=dynamic_value("model"),
        )


def test_disabled_runtime_fails_closed() -> None:
    runtime = VisualRuntime(
        analyzer=UnavailableVisualAnalyzer(),
        configuration=configuration(
            enabled=False
        ),
        record_writer=lambda record: None,
    )

    result = runtime.process_frame(
        frame=frame(),
        query=dynamic_value("query"),
        media_mode="single_image",
    )

    assert result.status == "unavailable"
    assert result.observation is None


def test_unavailable_provider_generates_no_claims() -> None:
    runtime = VisualRuntime(
        analyzer=UnavailableVisualAnalyzer(),
        configuration=configuration(
            enabled=True
        ),
        record_writer=lambda record: None,
    )

    result = runtime.process_frame(
        frame=frame(),
        query=dynamic_value("query"),
        media_mode="single_image",
    )

    assert result.status == "unavailable"
    assert result.observation is None


def test_valid_observation_is_stored() -> None:
    written_records: list[dict] = []

    runtime = VisualRuntime(
        analyzer=GeneratedAnalyzer(),
        configuration=configuration(
            enabled=True
        ),
        record_writer=written_records.append,
    )

    result = runtime.process_frame(
        frame=frame(),
        query=dynamic_value("query"),
        media_mode="single_image",
    )

    assert result.status == "success"
    assert result.observation is not None
    assert len(written_records) == 1
    assert (
        written_records[0]["record_type"]
        == "visual_observation"
    )
