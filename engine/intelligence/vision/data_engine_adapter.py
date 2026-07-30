from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engine.intelligence.vision.models import (
    EntityAssociation,
    MediaFrame,
    TemporalObservation,
    VisualObservation,
    VisualStateRecord,
)
from engine.intelligence.vision.validator import (
    validate_entity_association,
    validate_media_frame,
    validate_temporal_observation,
    validate_visual_observation,
    validate_visual_state,
)


def _record(
    *,
    record_id: str,
    record_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": record_id,
        "record_type": record_type,
        "source": "visual_analysis",
        "category": "runtime_evidence",
        "created_at": datetime.now(UTC).isoformat(),
        "data": data,
    }


def build_media_frame_record(
    frame: MediaFrame,
) -> dict[str, Any]:
    errors = validate_media_frame(frame)

    if errors:
        raise ValueError(
            "Invalid media frame:\n"
            + "\n".join(errors)
        )

    return _record(
        record_id=frame.frame_id,
        record_type="media_frame",
        data=frame.to_record(),
    )


def build_visual_observation_record(
    observation: VisualObservation,
) -> dict[str, Any]:
    errors = validate_visual_observation(
        observation
    )

    if errors:
        raise ValueError(
            "Invalid visual observation:\n"
            + "\n".join(errors)
        )

    return _record(
        record_id=observation.observation_id,
        record_type="visual_observation",
        data=observation.to_record(),
    )


def build_entity_association_record(
    association: EntityAssociation,
) -> dict[str, Any]:
    errors = validate_entity_association(
        association
    )

    if errors:
        raise ValueError(
            "Invalid entity association:\n"
            + "\n".join(errors)
        )

    return _record(
        record_id=association.association_id,
        record_type="visual_entity_association",
        data=association.to_record(),
    )


def build_temporal_observation_record(
    observation: TemporalObservation,
) -> dict[str, Any]:
    errors = validate_temporal_observation(
        observation
    )

    if errors:
        raise ValueError(
            "Invalid temporal observation:\n"
            + "\n".join(errors)
        )

    return _record(
        record_id=(
            observation.temporal_observation_id
        ),
        record_type="temporal_visual_observation",
        data=observation.to_record(),
    )


def build_visual_state_record(
    state: VisualStateRecord,
) -> dict[str, Any]:
    errors = validate_visual_state(state)

    if errors:
        raise ValueError(
            "Invalid visual state:\n"
            + "\n".join(errors)
        )

    return _record(
        record_id=state.state_id,
        record_type="visual_state",
        data=state.to_record(),
    )
