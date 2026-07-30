from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from engine.intelligence.vision.models import (
    VisualEntity,
    VisualObservation,
)
from engine.intelligence.vision.temporal_evidence import (
    build_temporal_observation,
)
from engine.intelligence.vision.validator import (
    validate_temporal_observation,
)


def dynamic_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def observation(
    *,
    request_id: str,
    sequence_id: str,
    query: str,
    frame_index: int,
    captured_at: str,
) -> VisualObservation:
    return VisualObservation(
        observation_id=dynamic_value("observation"),
        request_id=request_id,
        frame_id=dynamic_value("frame"),
        sequence_id=sequence_id,
        frame_index=frame_index,
        captured_at=captured_at,
        query=query,
        scene_description=dynamic_value("description"),
        entities=(
            VisualEntity(
                entity_id=dynamic_value("entity"),
                label=dynamic_value("label"),
                confidence=0.9,
            ),
        ),
        relations=(),
        visible_text=(),
        uncertainty=(),
        provider_name=dynamic_value("provider"),
        provider_model=dynamic_value("model"),
    )


def test_single_frame_cannot_create_temporal_evidence() -> None:
    now = datetime.now(UTC)

    item = observation(
        request_id=dynamic_value("request"),
        sequence_id=dynamic_value("sequence"),
        query=dynamic_value("query"),
        frame_index=0,
        captured_at=now.isoformat(),
    )

    with pytest.raises(ValueError):
        build_temporal_observation(
            observations=[item],
            description=dynamic_value("description"),
            confidence=0.8,
        )


def test_multiple_frames_create_temporal_evidence() -> None:
    now = datetime.now(UTC)
    request_id = dynamic_value("request")
    sequence_id = dynamic_value("sequence")
    query = dynamic_value("query")

    first = observation(
        request_id=request_id,
        sequence_id=sequence_id,
        query=query,
        frame_index=0,
        captured_at=now.isoformat(),
    )

    second = observation(
        request_id=request_id,
        sequence_id=sequence_id,
        query=query,
        frame_index=1,
        captured_at=(
            now + timedelta(seconds=1)
        ).isoformat(),
    )

    result = build_temporal_observation(
        observations=[first, second],
        description=dynamic_value("description"),
        confidence=0.82,
    )

    assert validate_temporal_observation(
        result
    ) == []

    assert len(
        result.supporting_observation_ids
    ) == 2
