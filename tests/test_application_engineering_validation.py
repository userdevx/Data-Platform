from __future__ import annotations

from uuid import uuid4

from engine.application_engineering.models import (
    EngineeringPlan,
    PlannedFileChange,
    RepositoryInspection,
    ValidationStep,
)
from engine.application_engineering.validation import (
    EngineeringPlanValidator,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4()}"


def build_inspection(
    *,
    requirement_id: str | None = None,
) -> RepositoryInspection:
    resolved_requirement_id = (
        requirement_id
        or runtime_value("requirement")
    )

    return RepositoryInspection.create(
        requirement_id=resolved_requirement_id,
        repository_root=runtime_value(
            "repository"
        ),
        inspected_paths=(
            "engine/application_engineering/models.py",
        ),
        findings=(
            "Planning models are available.",
        ),
    )


def build_plan(
    *,
    requirement_id: str,
    inspection_id: str,
    path: str = (
        "engine/application_engineering/validation.py"
    ),
    operation: str = "create",
) -> EngineeringPlan:
    return EngineeringPlan.create(
        requirement_id=requirement_id,
        inspection_id=inspection_id,
        summary="Validate an engineering plan.",
        planned_changes=(
            PlannedFileChange(
                path=path,
                operation=operation,
                purpose=(
                    "Add deterministic plan validation."
                ),
            ),
        ),
        validation_steps=(
            ValidationStep(
                description=(
                    "Run application engineering tests."
                ),
            ),
        ),
        risks=(),
    )


def test_valid_plan_passes_validation() -> None:
    requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=requirement_id
    )

    plan = build_plan(
        requirement_id=requirement_id,
        inspection_id=inspection.inspection_id,
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=requirement_id,
    )

    assert result.valid is True
    assert result.reasons == ()


def test_plan_requirement_mismatch_is_rejected() -> None:
    trusted_requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=trusted_requirement_id
    )

    plan = build_plan(
        requirement_id=runtime_value(
            "different-requirement"
        ),
        inspection_id=inspection.inspection_id,
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=trusted_requirement_id,
    )

    assert result.valid is False
    assert "plan_requirement_mismatch" in result.reasons


def test_inspection_requirement_mismatch_is_rejected() -> None:
    trusted_requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=runtime_value(
            "different-requirement"
        )
    )

    plan = build_plan(
        requirement_id=trusted_requirement_id,
        inspection_id=inspection.inspection_id,
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=trusted_requirement_id,
    )

    assert result.valid is False
    assert (
        "inspection_requirement_mismatch"
        in result.reasons
    )


def test_inspection_link_mismatch_is_rejected() -> None:
    requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=requirement_id
    )

    plan = build_plan(
        requirement_id=requirement_id,
        inspection_id=runtime_value(
            "different-inspection"
        ),
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=requirement_id,
    )

    assert result.valid is False
    assert "inspection_link_mismatch" in result.reasons


def test_absolute_planned_path_is_rejected() -> None:
    requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=requirement_id
    )

    plan = build_plan(
        requirement_id=requirement_id,
        inspection_id=inspection.inspection_id,
        path="/tmp/generated_file.py",
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=requirement_id,
    )

    assert result.valid is False
    assert "unsafe_planned_path" in result.reasons


def test_path_traversal_is_rejected() -> None:
    requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=requirement_id
    )

    plan = build_plan(
        requirement_id=requirement_id,
        inspection_id=inspection.inspection_id,
        path="../outside_repository.py",
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=requirement_id,
    )

    assert result.valid is False
    assert "unsafe_planned_path" in result.reasons


def test_conflicting_file_operations_are_rejected() -> None:
    requirement_id = runtime_value(
        "requirement"
    )

    inspection = build_inspection(
        requirement_id=requirement_id
    )

    shared_path = (
        "engine/application_engineering/validation.py"
    )

    plan = EngineeringPlan.create(
        requirement_id=requirement_id,
        inspection_id=inspection.inspection_id,
        summary="Reject conflicting file operations.",
        planned_changes=(
            PlannedFileChange(
                path=shared_path,
                operation="modify",
                purpose="Update validation behavior.",
            ),
            PlannedFileChange(
                path=shared_path,
                operation="delete",
                purpose="Remove the same file.",
            ),
        ),
        validation_steps=(
            ValidationStep(
                description=(
                    "Run application engineering tests."
                ),
            ),
        ),
        risks=(),
    )

    result = EngineeringPlanValidator().validate(
        plan=plan,
        inspection=inspection,
        requirement_id=requirement_id,
    )

    assert result.valid is False
    assert (
        "conflicting_file_operations"
        in result.reasons
    )
