from __future__ import annotations

from engine.model_development.learning_curriculum import (
    LearningAreaId,
    get_learning_area,
    get_learning_curriculum,
    validate_learning_curriculum,
)


def test_curriculum_contains_16_learning_areas(
) -> None:
    curriculum = (
        get_learning_curriculum()
    )

    assert len(
        curriculum
    ) == 16


def test_learning_area_ids_are_unique(
) -> None:
    curriculum = (
        get_learning_curriculum()
    )

    ids = [
        area.id
        for area
        in curriculum
    ]

    assert len(
        ids
    ) == len(
        set(
            ids
        )
    )


def test_every_learning_area_has_training_contract(
) -> None:
    for area in (
        get_learning_curriculum()
    ):
        assert area.title
        assert area.purpose
        assert area.behaviors
        assert area.required_inputs
        assert area.expected_outputs
        assert area.evaluation_requirements


def test_code_generation_contains_execution_feedback(
) -> None:
    area = get_learning_area(
        LearningAreaId.CODE_GENERATION
    )

    assert (
        area.requires_repository_context
        is True
    )

    assert (
        area.requires_execution_feedback
        is True
    )

    behavior_text = " ".join(
        area.behaviors
    ).lower()

    assert "query" in behavior_text
    assert "code" in behavior_text


def test_application_generation_requires_execution(
) -> None:
    area = get_learning_area(
        LearningAreaId
        .APPLICATION_GENERATION
    )

    assert (
        area.requires_repository_context
        is True
    )

    assert (
        area.requires_execution_feedback
        is True
    )


def test_learning_from_outcomes_requires_real_context(
) -> None:
    area = get_learning_area(
        LearningAreaId
        .LEARN_FROM_OUTCOMES
    )

    assert (
        area.requires_repository_context
        is True
    )

    assert (
        area.requires_data_engine_context
        is True
    )

    assert (
        area.requires_execution_feedback
        is True
    )


def test_curriculum_validation_passes(
) -> None:
    validate_learning_curriculum()
