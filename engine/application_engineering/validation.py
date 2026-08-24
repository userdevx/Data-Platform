from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.application_engineering.models import (
    EngineeringPlan,
    RepositoryInspection,
)


@dataclass(frozen=True)
class PlanValidationResult:
    valid: bool
    reasons: tuple[str, ...]


class EngineeringPlanValidator:
    def validate(
        self,
        *,
        plan: EngineeringPlan,
        inspection: RepositoryInspection,
        requirement_id: str,
    ) -> PlanValidationResult:
        if not isinstance(
            plan,
            EngineeringPlan,
        ):
            raise TypeError(
                "plan must be an EngineeringPlan."
            )

        if not isinstance(
            inspection,
            RepositoryInspection,
        ):
            raise TypeError(
                "inspection must be a "
                "RepositoryInspection."
            )

        if not isinstance(
            requirement_id,
            str,
        ):
            raise TypeError(
                "requirement_id must be a string."
            )

        normalized_requirement_id = (
            requirement_id.strip()
        )

        if not normalized_requirement_id:
            raise ValueError(
                "requirement_id cannot be empty."
            )

        reasons: list[str] = []

        self._validate_linkage(
            plan=plan,
            inspection=inspection,
            requirement_id=(
                normalized_requirement_id
            ),
            reasons=reasons,
        )

        self._validate_status(
            plan=plan,
            reasons=reasons,
        )

        self._validate_paths(
            plan=plan,
            reasons=reasons,
        )

        self._validate_conflicts(
            plan=plan,
            reasons=reasons,
        )

        return PlanValidationResult(
            valid=not reasons,
            reasons=tuple(
                reasons
            ),
        )


    @staticmethod
    def _validate_linkage(
        *,
        plan: EngineeringPlan,
        inspection: RepositoryInspection,
        requirement_id: str,
        reasons: list[str],
    ) -> None:
        if plan.requirement_id != requirement_id:
            reasons.append(
                "plan_requirement_mismatch"
            )

        if inspection.requirement_id != requirement_id:
            reasons.append(
                "inspection_requirement_mismatch"
            )

        if plan.inspection_id != inspection.inspection_id:
            reasons.append(
                "inspection_link_mismatch"
            )

    @staticmethod
    def _validate_status(
        *,
        plan: EngineeringPlan,
        reasons: list[str],
    ) -> None:
        if plan.status != "proposed":
            reasons.append(
                "invalid_plan_status"
            )


    @classmethod
    def _validate_paths(
        cls,
        *,
        plan: EngineeringPlan,
        reasons: list[str],
    ) -> None:
        for change in plan.planned_changes:
            if not cls._is_safe_relative_path(
                change.path
            ):
                reasons.append(
                    "unsafe_planned_path"
                )

    @staticmethod
    def _is_safe_relative_path(
        path_value: str,
    ) -> bool:
        candidate = Path(
            path_value
        )

        if candidate.is_absolute():
            return False

        if ".." in candidate.parts:
            return False

        if not candidate.parts:
            return False

        return True


    @staticmethod
    def _validate_conflicts(
        *,
        plan: EngineeringPlan,
        reasons: list[str],
    ) -> None:
        operations_by_path: dict[
            str,
            set[str],
        ] = {}

        for change in plan.planned_changes:
            normalized_path = (
                str(
                    Path(
                        change.path
                    )
                )
                .replace(
                    "\\",
                    "/",
                )
                .casefold()
            )

            operations = (
                operations_by_path.setdefault(
                    normalized_path,
                    set(),
                )
            )

            operations.add(
                change.operation
            )

        for operations in operations_by_path.values():
            if len(operations) > 1:
                reasons.append(
                    "conflicting_file_operations"
                )
                return
