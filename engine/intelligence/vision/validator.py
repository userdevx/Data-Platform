from __future__ import annotations

from datetime import datetime

from engine.intelligence.vision.models import (
    EntityAssociation,
    MediaFrame,
    TemporalObservation,
    VisualObservation,
    VisualStateRecord,
)


def _valid_confidence(value: float) -> bool:
    return 0.0 <= value <= 1.0


def _valid_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return False

    return True


def validate_media_frame(
    frame: MediaFrame,
) -> list[str]:
    errors: list[str] = []

    required = {
        "frame_id": frame.frame_id,
        "source_id": frame.source_id,
        "sequence_id": frame.sequence_id,
        "captured_at": frame.captured_at,
        "media_location": frame.media_location,
        "media_type": frame.media_type,
    }

    for name, value in required.items():
        if not value.strip():
            errors.append(f"{name} is required.")

    if frame.frame_index < 0:
        errors.append(
            "frame_index cannot be negative."
        )

    if (
        frame.captured_at
        and not _valid_datetime(frame.captured_at)
    ):
        errors.append(
            "captured_at must be a valid ISO datetime."
        )

    return errors


def validate_visual_observation(
    observation: VisualObservation,
    *,
    minimum_entity_confidence: float = 0.0,
    minimum_relation_confidence: float = 0.0,
) -> list[str]:
    errors: list[str] = []

    required = {
        "observation_id": observation.observation_id,
        "request_id": observation.request_id,
        "frame_id": observation.frame_id,
        "sequence_id": observation.sequence_id,
        "captured_at": observation.captured_at,
        "query": observation.query,
        "scene_description": (
            observation.scene_description
        ),
        "provider_name": observation.provider_name,
        "provider_model": observation.provider_model,
    }

    for name, value in required.items():
        if not value.strip():
            errors.append(f"{name} is required.")

    if observation.frame_index < 0:
        errors.append(
            "frame_index cannot be negative."
        )

    if (
        observation.captured_at
        and not _valid_datetime(
            observation.captured_at
        )
    ):
        errors.append(
            "captured_at must be a valid ISO datetime."
        )

    entity_ids = [
        entity.entity_id
        for entity in observation.entities
    ]

    if len(entity_ids) != len(set(entity_ids)):
        errors.append(
            "Entity identifiers must be unique."
        )

    valid_entity_ids = set(entity_ids)

    for entity in observation.entities:
        if not entity.entity_id.strip():
            errors.append(
                "Every entity requires an entity_id."
            )

        if not entity.label.strip():
            errors.append(
                "Every entity requires a runtime label."
            )

        if not _valid_confidence(
            entity.confidence
        ):
            errors.append(
                "Entity confidence must be between 0 and 1."
            )

        if (
            entity.confidence
            < minimum_entity_confidence
        ):
            errors.append(
                "Entity confidence is below the "
                "configured minimum."
            )

    for relation in observation.relations:
        if relation.subject_id not in valid_entity_ids:
            errors.append(
                "Relation subject must reference "
                "an entity in the observation."
            )

        if (
            relation.object_id is not None
            and relation.object_id not in valid_entity_ids
        ):
            errors.append(
                "Relation object must reference "
                "an entity in the observation."
            )

        if not relation.predicate.strip():
            errors.append(
                "Every relation requires a runtime predicate."
            )

        if not _valid_confidence(
            relation.confidence
        ):
            errors.append(
                "Relation confidence must be between 0 and 1."
            )

        if (
            relation.confidence
            < minimum_relation_confidence
        ):
            errors.append(
                "Relation confidence is below the "
                "configured minimum."
            )

    return errors


def validate_entity_association(
    association: EntityAssociation,
) -> list[str]:
    errors: list[str] = []

    required = {
        "association_id": association.association_id,
        "sequence_id": association.sequence_id,
        "previous_observation_id": (
            association.previous_observation_id
        ),
        "current_observation_id": (
            association.current_observation_id
        ),
        "previous_entity_id": (
            association.previous_entity_id
        ),
        "current_entity_id": (
            association.current_entity_id
        ),
    }

    for name, value in required.items():
        if not value.strip():
            errors.append(f"{name} is required.")

    if not _valid_confidence(
        association.confidence
    ):
        errors.append(
            "Association confidence must be between 0 and 1."
        )

    return errors


def validate_temporal_observation(
    observation: TemporalObservation,
    *,
    minimum_frames: int = 2,
) -> list[str]:
    errors: list[str] = []

    required = {
        "temporal_observation_id": (
            observation.temporal_observation_id
        ),
        "request_id": observation.request_id,
        "sequence_id": observation.sequence_id,
        "query": observation.query,
        "description": observation.description,
        "started_at": observation.started_at,
        "ended_at": observation.ended_at,
    }

    for name, value in required.items():
        if not value.strip():
            errors.append(f"{name} is required.")

    if (
        len(observation.supporting_observation_ids)
        < minimum_frames
    ):
        errors.append(
            "Temporal evidence has too few "
            "supporting observations."
        )

    if (
        len(observation.supporting_frame_ids)
        < minimum_frames
    ):
        errors.append(
            "Temporal evidence has too few "
            "supporting frames."
        )

    if not _valid_confidence(
        observation.confidence
    ):
        errors.append(
            "Temporal confidence must be between 0 and 1."
        )

    if (
        _valid_datetime(observation.started_at)
        and _valid_datetime(observation.ended_at)
    ):
        started = datetime.fromisoformat(
            observation.started_at.replace(
                "Z",
                "+00:00",
            )
        )
        ended = datetime.fromisoformat(
            observation.ended_at.replace(
                "Z",
                "+00:00",
            )
        )

        if ended < started:
            errors.append(
                "ended_at cannot occur before started_at."
            )

    return errors


def validate_visual_state(
    state: VisualStateRecord,
) -> list[str]:
    errors: list[str] = []

    if not state.state_id.strip():
        errors.append("state_id is required.")

    if not state.request_id.strip():
        errors.append("request_id is required.")

    if not state.sequence_id.strip():
        errors.append("sequence_id is required.")

    if not state.query.strip():
        errors.append("query is required.")

    if not state.description.strip():
        errors.append("description is required.")

    if not state.status.strip():
        errors.append("status is required.")

    if not state.observation_ids:
        errors.append(
            "At least one observation is required."
        )

    if not _valid_confidence(state.confidence):
        errors.append(
            "State confidence must be between 0 and 1."
        )

    return errors
