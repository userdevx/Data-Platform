from uuid import uuid4

import pytest

from engine.application_engineering.models import (
    EngineeringPlan,
    PlannedFileChange,
    RepositoryInspection,
    ValidationStep,
)


def runtime_value(
    prefix: str,
) -> str:
    return f"{prefix}-{uuid4().hex}"


def create_inspection() -> RepositoryInspection:
    return RepositoryInspection.create(
        requirement_id=runtime_value(
            "requirement"
        ),
        repository_root=runtime_value(
            "repository"
        ),
        inspected_paths=(
            runtime_value(
                "path"
            ),
        ),
        findings=(
            runtime_value(
                "finding"
            ),
        ),
    )


def create_change() -> PlannedFileChange:
    return PlannedFileChange(
        path=runtime_value(
            "path"
        ),
        operation="modify",
        purpose=runtime_value(
            "purpose"
        ),
    )


def create_validation_step() -> ValidationStep:
    return ValidationStep(
        description=runtime_value(
            "validation"
        ),
        command=None,
    )


def create_plan() -> EngineeringPlan:
    inspection = create_inspection()

    return EngineeringPlan.create(
        requirement_id=(
            inspection.requirement_id
        ),
        inspection_id=(
            inspection.inspection_id
        ),
        summary=runtime_value(
            "summary"
        ),
        planned_changes=(
            create_change(),
        ),
        validation_steps=(
            create_validation_step(),
        ),
        risks=(
            runtime_value(
                "risk"
            ),
        ),
    )


def test_repository_inspection_creation():
    inspection = create_inspection()

    assert inspection.inspection_id
    assert inspection.requirement_id
    assert inspection.repository_root
    assert inspection.inspected_paths
    assert inspection.created_at


def test_repository_inspection_requires_paths():
    with pytest.raises(
        ValueError
    ):
        RepositoryInspection.create(
            requirement_id=runtime_value(
                "requirement"
            ),
            repository_root=runtime_value(
                "repository"
            ),
            inspected_paths=(),
            findings=(),
        )


def test_repository_inspection_rejects_empty_requirement():
    with pytest.raises(
        ValueError
    ):
        RepositoryInspection.create(
            requirement_id="   ",
            repository_root=runtime_value(
                "repository"
            ),
            inspected_paths=(
                runtime_value(
                    "path"
                ),
            ),
            findings=(),
        )


@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "modify",
        "delete",
        "move",
    ],
)
def test_planned_file_change_accepts_supported_operations(
    operation: str,
):
    change = PlannedFileChange(
        path=runtime_value(
            "path"
        ),
        operation=operation,
        purpose=runtime_value(
            "purpose"
        ),
    )

    assert change.operation == operation


def test_planned_file_change_normalizes_operation():
    change = PlannedFileChange(
        path=runtime_value(
            "path"
        ),
        operation="  MODIFY  ",
        purpose=runtime_value(
            "purpose"
        ),
    )

    assert change.operation == "modify"


def test_planned_file_change_rejects_unknown_operation():
    with pytest.raises(
        ValueError
    ):
        PlannedFileChange(
            path=runtime_value(
                "path"
            ),
            operation=runtime_value(
                "operation"
            ),
            purpose=runtime_value(
                "purpose"
            ),
        )


def test_validation_step_allows_no_command():
    step = ValidationStep(
        description=runtime_value(
            "description"
        )
    )

    assert step.command is None


def test_validation_step_rejects_empty_description():
    with pytest.raises(
        ValueError
    ):
        ValidationStep(
            description="   "
        )


def test_engineering_plan_creation():
    plan = create_plan()

    assert plan.plan_id
    assert plan.requirement_id
    assert plan.inspection_id
    assert plan.status == "proposed"
    assert len(
        plan.planned_changes
    ) == 1
    assert len(
        plan.validation_steps
    ) == 1


def test_engineering_plan_requires_planned_changes():
    inspection = create_inspection()

    with pytest.raises(
        ValueError
    ):
        EngineeringPlan.create(
            requirement_id=(
                inspection.requirement_id
            ),
            inspection_id=(
                inspection.inspection_id
            ),
            summary=runtime_value(
                "summary"
            ),
            planned_changes=(),
            validation_steps=(
                create_validation_step(),
            ),
        )


def test_engineering_plan_requires_validation_steps():
    inspection = create_inspection()

    with pytest.raises(
        ValueError
    ):
        EngineeringPlan.create(
            requirement_id=(
                inspection.requirement_id
            ),
            inspection_id=(
                inspection.inspection_id
            ),
            summary=runtime_value(
                "summary"
            ),
            planned_changes=(
                create_change(),
            ),
            validation_steps=(),
        )


def test_engineering_plan_rejects_invalid_change_type():
    inspection = create_inspection()

    with pytest.raises(
        TypeError
    ):
        EngineeringPlan.create(
            requirement_id=(
                inspection.requirement_id
            ),
            inspection_id=(
                inspection.inspection_id
            ),
            summary=runtime_value(
                "summary"
            ),
            planned_changes=(
                runtime_value(
                    "invalid"
                ),
            ),
            validation_steps=(
                create_validation_step(),
            ),
        )


def test_engineering_plan_rejects_invalid_validation_type():
    inspection = create_inspection()

    with pytest.raises(
        TypeError
    ):
        EngineeringPlan.create(
            requirement_id=(
                inspection.requirement_id
            ),
            inspection_id=(
                inspection.inspection_id
            ),
            summary=runtime_value(
                "summary"
            ),
            planned_changes=(
                create_change(),
            ),
            validation_steps=(
                runtime_value(
                    "invalid"
                ),
            ),
        )


def test_new_engineering_plan_cannot_start_authorized():
    inspection = create_inspection()

    with pytest.raises(
        ValueError
    ):
        EngineeringPlan(
            plan_id=runtime_value(
                "plan"
            ),
            requirement_id=(
                inspection.requirement_id
            ),
            inspection_id=(
                inspection.inspection_id
            ),
            summary=runtime_value(
                "summary"
            ),
            planned_changes=(
                create_change(),
            ),
            validation_steps=(
                create_validation_step(),
            ),
            risks=(),
            status="authorized",
        )


def test_to_dict_serializes_nested_models():
    plan = create_plan()

    payload = plan.to_dict()

    assert isinstance(
        payload,
        dict,
    )

    assert isinstance(
        payload[
            "planned_changes"
        ],
        tuple,
    )

    assert (
        payload[
            "planned_changes"
        ][0]["operation"]
        == "modify"
    )

    assert isinstance(
        payload[
            "validation_steps"
        ],
        tuple,
    )
