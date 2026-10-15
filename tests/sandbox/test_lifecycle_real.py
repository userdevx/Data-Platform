from __future__ import annotations

from pathlib import Path

import pytest

from engine.sandbox.lifecycle import (
    ExecutionLifecycle,
    ExecutionState,
    LifecycleError,
    ResourcePolicy,
    ResourcePolicyError,
    WorkspaceLease,
)
from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)


def _request(**limit_changes) -> SandboxRequest:
    limit_values = {
        "cpu_count": 1.0,
        "memory_mb": 256,
        "timeout_seconds": 10,
        "pids": 16,
    }

    limit_values.update(
        limit_changes
    )

    return SandboxRequest(
        workload_type=WorkloadType.TEST,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "/bin/sh",
            "-c",
            "printf 'TASK12_RESOURCE_POLICY_OK\\n'",
        ),
        network_enabled=False,
        writable_workspace=False,
        limits=ResourceLimits(
            **limit_values
        ),
    )


def test_lifecycle_happy_path() -> None:
    lifecycle = ExecutionLifecycle()
    record = lifecycle.create()

    for state in (
        ExecutionState.VALIDATED,
        ExecutionState.PREPARING,
        ExecutionState.RUNNING,
        ExecutionState.FINISHED,
        ExecutionState.CLEANED,
    ):
        lifecycle.transition(
            record,
            state,
        )

    assert (
        record.state
        is ExecutionState.CLEANED
    )


def test_lifecycle_refuses_invalid_transition() -> None:
    lifecycle = ExecutionLifecycle()
    record = lifecycle.create()

    with pytest.raises(
        LifecycleError
    ):
        lifecycle.transition(
            record,
            ExecutionState.RUNNING,
        )


def test_resource_policy_real_values() -> None:
    request = _request()

    assert isinstance(
        request,
        SandboxRequest,
    )

    assert isinstance(
        request.limits,
        ResourceLimits,
    )

    ResourcePolicy().validate(
        request
    )

    print(
        "REAL_RESOURCE_POLICY_VALUES_OK"
    )


def test_resource_policy_rejects_zero_pids() -> None:
    request = _request(
        pids=0
    )

    with pytest.raises(
        ResourcePolicyError
    ):
        ResourcePolicy().validate(
            request
        )

    print(
        "REAL_RESOURCE_POLICY_ZERO_PIDS_REJECTED_OK"
    )


def test_workspace_is_real_and_removed(
    tmp_path: Path,
) -> None:
    with WorkspaceLease.create(
        root=tmp_path
    ) as workspace:
        marker = (
            workspace.path
            / "marker"
        )

        marker.write_text(
            "sandbox",
            encoding="utf-8",
        )

        assert (
            marker.read_text(
                encoding="utf-8"
            )
            == "sandbox"
        )

        path = workspace.path

    assert not path.exists()

    print(
        "REAL_WORKSPACE_LEASE_CLEANUP_OK"
    )
