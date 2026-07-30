from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from engine.intelligence.vision.models import (
    TemporalObservation,
    VisualStateRecord,
)


def start_visual_state(
    observation: TemporalObservation,
) -> VisualStateRecord:
    return VisualStateRecord(
        state_id=uuid4().hex,
        request_id=observation.request_id,
        sequence_id=observation.sequence_id,
        query=observation.query,
        description=observation.description,
        status="active",
        first_observed_at=observation.started_at,
        last_observed_at=observation.ended_at,
        observation_ids=(
            observation.supporting_observation_ids
        ),
        confidence=observation.confidence,
        uncertainty=observation.uncertainty,
    )


def update_visual_state(
    *,
    current_state: VisualStateRecord,
    observation: TemporalObservation,
) -> VisualStateRecord:
    if current_state.sequence_id != observation.sequence_id:
        raise ValueError(
            "State and observation belong to different sequences."
        )

    if current_state.request_id != observation.request_id:
        raise ValueError(
            "State and observation belong to different requests."
        )

    merged_ids = tuple(
        dict.fromkeys(
            current_state.observation_ids
            + observation.supporting_observation_ids
        )
    )

    merged_uncertainty = tuple(
        dict.fromkeys(
            current_state.uncertainty
            + observation.uncertainty
        )
    )

    combined_confidence = (
        current_state.confidence
        + observation.confidence
    ) / 2

    return replace(
        current_state,
        description=observation.description,
        last_observed_at=observation.ended_at,
        observation_ids=merged_ids,
        confidence=combined_confidence,
        uncertainty=merged_uncertainty,
    )


def end_visual_state(
    *,
    current_state: VisualStateRecord,
    ended_at: str,
) -> VisualStateRecord:
    return replace(
        current_state,
        status="ended",
        last_observed_at=ended_at,
    )
