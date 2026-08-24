from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from typing import Any
from uuid import uuid4


_ALLOWED_FILE_OPERATIONS = frozenset(
    {
        "create",
        "modify",
        "delete",
        "move",
    }
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def require_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{field_name} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return normalized


def require_text_tuple(
    value: Any,
    *,
    field_name: str,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if not isinstance(
        value,
        tuple,
    ):
        raise TypeError(
            f"{field_name} must be a tuple."
        )

    normalized = tuple(
        require_text(
            item,
            field_name=field_name,
        )
        for item in value
    )

    if not allow_empty and not normalized:
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return normalized


@dataclass(frozen=True)
class RepositoryInspection:
    inspection_id: str
    requirement_id: str
    repository_root: str
    inspected_paths: tuple[str, ...]
    findings: tuple[str, ...]
    created_at: str = field(
        default_factory=utc_now
    )

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "inspection_id",
            require_text(
                self.inspection_id,
                field_name="inspection_id",
            ),
        )

        object.__setattr__(
            self,
            "requirement_id",
            require_text(
                self.requirement_id,
                field_name="requirement_id",
            ),
        )

        object.__setattr__(
            self,
            "repository_root",
            require_text(
                self.repository_root,
                field_name="repository_root",
            ),
        )

        object.__setattr__(
            self,
            "inspected_paths",
            require_text_tuple(
                self.inspected_paths,
                field_name="inspected_paths",
                allow_empty=False,
            ),
        )

        object.__setattr__(
            self,
            "findings",
            require_text_tuple(
                self.findings,
                field_name="findings",
            ),
        )

        object.__setattr__(
            self,
            "created_at",
            require_text(
                self.created_at,
                field_name="created_at",
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        requirement_id: str,
        repository_root: str,
        inspected_paths: tuple[str, ...],
        findings: tuple[str, ...],
    ) -> "RepositoryInspection":
        return cls(
            inspection_id=str(uuid4()),
            requirement_id=requirement_id,
            repository_root=repository_root,
            inspected_paths=inspected_paths,
            findings=findings,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlannedFileChange:
    path: str
    operation: str
    purpose: str

    def __post_init__(
        self,
    ) -> None:
        normalized_path = require_text(
            self.path,
            field_name="path",
        )

        normalized_operation = require_text(
            self.operation,
            field_name="operation",
        ).casefold()

        if normalized_operation not in _ALLOWED_FILE_OPERATIONS:
            raise ValueError(
                "operation must be one of: "
                f"{sorted(_ALLOWED_FILE_OPERATIONS)}"
            )

        normalized_purpose = require_text(
            self.purpose,
            field_name="purpose",
        )

        object.__setattr__(
            self,
            "path",
            normalized_path,
        )
        object.__setattr__(
            self,
            "operation",
            normalized_operation,
        )
        object.__setattr__(
            self,
            "purpose",
            normalized_purpose,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationStep:
    description: str
    command: str | None = None

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "description",
            require_text(
                self.description,
                field_name="description",
            ),
        )

        if self.command is not None:
            object.__setattr__(
                self,
                "command",
                require_text(
                    self.command,
                    field_name="command",
                ),
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EngineeringPlan:
    plan_id: str
    requirement_id: str
    inspection_id: str
    summary: str
    planned_changes: tuple[
        PlannedFileChange,
        ...,
    ]
    validation_steps: tuple[
        ValidationStep,
        ...,
    ]
    risks: tuple[str, ...]
    status: str = "proposed"
    created_at: str = field(
        default_factory=utc_now
    )

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "plan_id",
            require_text(
                self.plan_id,
                field_name="plan_id",
            ),
        )
        object.__setattr__(
            self,
            "requirement_id",
            require_text(
                self.requirement_id,
                field_name="requirement_id",
            ),
        )
        object.__setattr__(
            self,
            "inspection_id",
            require_text(
                self.inspection_id,
                field_name="inspection_id",
            ),
        )
        object.__setattr__(
            self,
            "summary",
            require_text(
                self.summary,
                field_name="summary",
            ),
        )

        if not isinstance(
            self.planned_changes,
            tuple,
        ):
            raise TypeError(
                "planned_changes must be a tuple."
            )

        if not self.planned_changes:
            raise ValueError(
                "planned_changes cannot be empty."
            )

        for change in self.planned_changes:
            if not isinstance(
                change,
                PlannedFileChange,
            ):
                raise TypeError(
                    "planned_changes must contain "
                    "PlannedFileChange objects."
                )

        if not isinstance(
            self.validation_steps,
            tuple,
        ):
            raise TypeError(
                "validation_steps must be a tuple."
            )

        if not self.validation_steps:
            raise ValueError(
                "validation_steps cannot be empty."
            )

        for step in self.validation_steps:
            if not isinstance(
                step,
                ValidationStep,
            ):
                raise TypeError(
                    "validation_steps must contain "
                    "ValidationStep objects."
                )

        object.__setattr__(
            self,
            "risks",
            require_text_tuple(
                self.risks,
                field_name="risks",
            ),
        )

        normalized_status = require_text(
            self.status,
            field_name="status",
        ).casefold()

        if normalized_status != "proposed":
            raise ValueError(
                "New engineering plans must begin "
                "with status 'proposed'."
            )

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )
        object.__setattr__(
            self,
            "created_at",
            require_text(
                self.created_at,
                field_name="created_at",
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        requirement_id: str,
        inspection_id: str,
        summary: str,
        planned_changes: tuple[
            PlannedFileChange,
            ...,
        ],
        validation_steps: tuple[
            ValidationStep,
            ...,
        ],
        risks: tuple[str, ...] = (),
    ) -> "EngineeringPlan":
        return cls(
            plan_id=str(uuid4()),
            requirement_id=requirement_id,
            inspection_id=inspection_id,
            summary=summary,
            planned_changes=planned_changes,
            validation_steps=validation_steps,
            risks=risks,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)
