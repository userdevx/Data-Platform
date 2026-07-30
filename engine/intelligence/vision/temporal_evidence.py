from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from engine.intelligence.vision.models import (
    TemporalObservation,
    VisualObservation,
)
from engine.intelligence.vision.validator import (
    validate_visual_observation,
)


def build_temporal_observation(
    *,
    observations: Sequence[VisualObservation],
    description: str,
    confidence: float,
    uncertainty: tuple[str, ...] = (),
) -> TemporalObservation:
    if len(observations) < 2:
        raise ValueError(
            "At least two observations are required."
        )

    sequence_ids = {
        observation.sequence_id
        for observation in observations
    }

    request_ids = {
        observation.request_id
        for observation in observations
    }

    queries = {
        observation.query
        for observation in observations
    }

    if len(sequence_ids) != 1:
        raise ValueError(
            "Observations must belong to one sequence."
        )

    if len(request_ids) != 1:
        raise ValueError(
            "Observations must belong to one request."
        )

    if len(queries) != 1:
        raise ValueError(
            "Observations must use one query."
        )

    clean_description = " ".join(
        description.split()
    ).strip()

    if not clean_description:
        raise ValueError(
            "description is required."
        )

    ordered = sorted(
        observations,
        key=lambda item: item.frame_index,
    )

    indexes = [
        observation.frame_index
        for observation in ordered
    ]

    if len(indexes) != len(set(indexes)):
        raise ValueError(
            "Frame indexes must be unique."
        )

    for observation in ordered:
        errors = validate_visual_observation(
            observation
        )

        if errors:
            raise ValueError(
                "Invalid visual observation:\n"
                + "\n".join(errors)
            )

    return TemporalObservation(
        temporal_observation_id=uuid4().hex,
        request_id=ordered[0].request_id,
        sequence_id=ordered[0].sequence_id,
        query=ordered[0].query,
        supporting_observation_ids=tuple(
            item.observation_id
            for item in ordered
        ),
        supporting_frame_ids=tuple(
            item.frame_id
            for item in ordered
        ),
        description=clean_description,
        confidence=confidence,
        uncertainty=uncertainty,
        started_at=ordered[0].captured_at,
        ended_at=ordered[-1].captured_at,
        metadata={
            "supporting_frame_count": len(ordered),
        },
    )
