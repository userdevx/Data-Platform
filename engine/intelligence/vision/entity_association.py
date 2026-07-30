from __future__ import annotations

from difflib import SequenceMatcher
from uuid import uuid4

from engine.intelligence.vision.models import (
    EntityAssociation,
    VisualEntity,
    VisualObservation,
)


def _normalized_text(value: str) -> str:
    return " ".join(
        value.casefold().split()
    )


def _label_similarity(
    first: VisualEntity,
    second: VisualEntity,
) -> float:
    return SequenceMatcher(
        None,
        _normalized_text(first.label),
        _normalized_text(second.label),
    ).ratio()


def associate_entities(
    *,
    previous: VisualObservation,
    current: VisualObservation,
    minimum_similarity: float = 0.75,
) -> tuple[EntityAssociation, ...]:
    if previous.sequence_id != current.sequence_id:
        raise ValueError(
            "Observations belong to different sequences."
        )

    if not 0.0 <= minimum_similarity <= 1.0:
        raise ValueError(
            "minimum_similarity must be between 0 and 1."
        )

    associations: list[EntityAssociation] = []
    assigned_current_ids: set[str] = set()

    for previous_entity in previous.entities:
        best_entity: VisualEntity | None = None
        best_score = 0.0

        for current_entity in current.entities:
            if current_entity.entity_id in assigned_current_ids:
                continue

            score = _label_similarity(
                previous_entity,
                current_entity,
            )

            if score > best_score:
                best_entity = current_entity
                best_score = score

        if (
            best_entity is None
            or best_score < minimum_similarity
        ):
            continue

        assigned_current_ids.add(
            best_entity.entity_id
        )

        associations.append(
            EntityAssociation(
                association_id=uuid4().hex,
                sequence_id=current.sequence_id,
                previous_observation_id=(
                    previous.observation_id
                ),
                current_observation_id=(
                    current.observation_id
                ),
                previous_entity_id=(
                    previous_entity.entity_id
                ),
                current_entity_id=(
                    best_entity.entity_id
                ),
                confidence=best_score,
                evidence=(
                    "runtime_label_similarity",
                ),
            )
        )

    return tuple(associations)
