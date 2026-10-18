from __future__ import annotations

import pytest

from engine.sandbox.pro_layer import (
    ApprovalRequired,
    ApprovalStatus,
    ApprovalStore,
)


def test_explicit_human_approval() -> None:
    store = ApprovalStore()

    approval = store.request(
        execution_id="exec-1",
        action="apply code change",
    )

    assert approval.status is ApprovalStatus.PENDING

    with pytest.raises(ApprovalRequired):
        store.require_approved(approval.approval_id)

    decided = store.decide(
        approval.approval_id,
        approved=True,
        decided_by="human",
    )

    assert decided.status is ApprovalStatus.APPROVED

    store.require_approved(approval.approval_id)


def test_decision_cannot_be_changed() -> None:
    store = ApprovalStore()

    approval = store.request(
        execution_id="exec-1",
        action="execute",
    )

    store.decide(
        approval.approval_id,
        approved=False,
        decided_by="human",
    )

    with pytest.raises(ValueError):
        store.decide(
            approval.approval_id,
            approved=True,
            decided_by="human",
        )
