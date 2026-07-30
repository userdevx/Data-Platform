from datetime import UTC, datetime
from uuid import uuid4

from engine.intelligence.vision.models import (
    MediaFrame,
    VisualEntity,
    VisualObservation,
    VisualRelation,
)
from engine.intelligence.vision.validator import (
    validate_media_frame,
    validate_visual_observation,
)


def dynamic_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_frame() -> MediaFrame:
    return MediaFrame(
        frame_id=dynamic_value("frame"),
        source_id=dynamic_value("source"),
        sequence_id=dynamic_value("sequence"),
        frame_index=0,
        captured_at=datetime.now(UTC).isoformat(),
        media_location=dynamic_value("location"),
        media_type="image/test",
    )


def build_observation() -> VisualObservation:
    first_id = dynamic_value("entity")
    second_id = dynamic_value("entity")
    frame = build_frame()

    return VisualObservation(
        observation_id=dynamic_value("observation"),
        request_id=dynamic_value("request"),
        frame_id=frame.frame_id,
        sequence_id=frame.sequence_id,
        frame_index=frame.frame_index,
        captured_at=frame.captured_at,
        query=dynamic_value("query"),
        scene_description=dynamic_value("description"),
        entities=(
            VisualEntity(
                entity_id=first_id,
                label=dynamic_value("label"),
                confidence=0.91,
            ),
            VisualEntity(
                entity_id=second_id,
                label=dynamic_value("label"),
                confidence=0.83,
            ),
        ),
        relations=(
            VisualRelation(
                subject_id=first_id,
                predicate=dynamic_value("predicate"),
                object_id=second_id,
                confidence=0.79,
            ),
        ),
        visible_text=(
            dynamic_value("visible-text"),
        ),
        uncertainty=(
            dynamic_value("uncertainty"),
        ),
        provider_name=dynamic_value("provider"),
        provider_model=dynamic_value("model"),
    )


def test_valid_frame_passes_validation() -> None:
    assert validate_media_frame(
        build_frame()
    ) == []


def test_valid_observation_passes_validation() -> None:
    assert validate_visual_observation(
        build_observation()
    ) == []


def test_duplicate_entity_identifiers_are_rejected() -> None:
    observation = build_observation()
    repeated = observation.entities[0]

    invalid = VisualObservation(
        observation_id=observation.observation_id,
        request_id=observation.request_id,
        frame_id=observation.frame_id,
        sequence_id=observation.sequence_id,
        frame_index=observation.frame_index,
        captured_at=observation.captured_at,
        query=observation.query,
        scene_description=observation.scene_description,
        entities=(repeated, repeated),
        relations=(),
        visible_text=(),
        uncertainty=(),
        provider_name=observation.provider_name,
        provider_model=observation.provider_model,
    )

    errors = validate_visual_observation(
        invalid
    )

    assert any(
        "unique" in error.lower()
        for error in errors
    )


def test_invalid_relation_reference_is_rejected() -> None:
    observation = build_observation()

    invalid_relation = VisualRelation(
        subject_id=dynamic_value("missing"),
        predicate=dynamic_value("predicate"),
        object_id=None,
        confidence=0.75,
    )

    invalid = VisualObservation(
        observation_id=observation.observation_id,
        request_id=observation.request_id,
        frame_id=observation.frame_id,
        sequence_id=observation.sequence_id,
        frame_index=observation.frame_index,
        captured_at=observation.captured_at,
        query=observation.query,
        scene_description=observation.scene_description,
        entities=observation.entities,
        relations=(invalid_relation,),
        visible_text=(),
        uncertainty=(),
        provider_name=observation.provider_name,
        provider_model=observation.provider_model,
    )

    errors = validate_visual_observation(
        invalid
    )

    assert any(
        "subject" in error.lower()
        for error in errors
    )
