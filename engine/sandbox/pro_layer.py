from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalRequired(PermissionError):
    pass


@dataclass(frozen=True)
class Approval:
    approval_id: str
    execution_id: str
    action: str
    status: ApprovalStatus
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None


class ApprovalStore:
    def __init__(self) -> None:
        self._approvals: dict[str, Approval] = {}

    def request(
        self,
        *,
        execution_id: str,
        action: str,
    ) -> Approval:
        approval = Approval(
            approval_id=str(uuid4()),
            execution_id=execution_id,
            action=action,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(
                timezone.utc
            ).isoformat(),
        )

        self._approvals[approval.approval_id] = approval

        return approval

    def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str,
    ) -> Approval:
        current = self._approvals[approval_id]

        if current.status is not ApprovalStatus.PENDING:
            raise ValueError(
                "approval decision is immutable once decided"
            )

        updated = Approval(
            approval_id=current.approval_id,
            execution_id=current.execution_id,
            action=current.action,
            status=(
                ApprovalStatus.APPROVED
                if approved
                else ApprovalStatus.DENIED
            ),
            created_at=current.created_at,
            decided_at=datetime.now(
                timezone.utc
            ).isoformat(),
            decided_by=decided_by,
        )

        self._approvals[approval_id] = updated

        return updated

    def require_approved(self, approval_id: str) -> None:
        approval = self._approvals[approval_id]

        if approval.status is not ApprovalStatus.APPROVED:
            raise ApprovalRequired(
                f"approval is not approved: {approval_id}"
            )
