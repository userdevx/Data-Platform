from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.sandbox.evidence import (
    EvidenceIntegrityError,
    EvidenceRecorder,
)


def _recorder(
    tmp_path: Path,
) -> EvidenceRecorder:
    return EvidenceRecorder(
        tmp_path / "ledger" / "evidence.jsonl",
        anchor_path=(
            tmp_path
            / "anchor"
            / "evidence.head"
        ),
    )


def test_real_evidence_chain(
    tmp_path: Path,
) -> None:
    recorder = _recorder(
        tmp_path
    )

    first = recorder.append(
        event_type="sandbox.started",
        execution_id="exec-1",
        data={
            "runtime": "firecracker"
        },
    )

    second = recorder.append(
        event_type="sandbox.finished",
        execution_id="exec-1",
        data={
            "exit_code": 0
        },
    )

    assert (
        second.previous_hash
        == first.record_hash
    )

    assert recorder.verify() == 2

    print(
        "REAL_EVIDENCE_CHAIN_OK"
    )


def test_tampered_evidence_is_rejected(
    tmp_path: Path,
) -> None:
    recorder = _recorder(
        tmp_path
    )

    recorder.append(
        event_type="sandbox.finished",
        execution_id="exec-1",
        data={
            "exit_code": 0
        },
    )

    lines = recorder.path.read_text(
        encoding="utf-8"
    ).splitlines()

    record = json.loads(
        lines[0]
    )

    record["data"]["exit_code"] = 99

    recorder.path.write_text(
        json.dumps(
            record
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        EvidenceIntegrityError
    ):
        recorder.verify()

    print(
        "REAL_EVIDENCE_TAMPER_REJECTED_OK"
    )


def test_truncated_tail_is_rejected(
    tmp_path: Path,
) -> None:
    recorder = _recorder(
        tmp_path
    )

    recorder.append(
        event_type="sandbox.started",
        execution_id="exec-1",
        data={},
    )

    recorder.append(
        event_type="sandbox.finished",
        execution_id="exec-1",
        data={},
    )

    lines = recorder.path.read_text(
        encoding="utf-8"
    ).splitlines()

    recorder.path.write_text(
        lines[0] + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        EvidenceIntegrityError,
        match="length",
    ):
        recorder.verify()

    print(
        "REAL_EVIDENCE_TRUNCATION_REJECTED_OK"
    )


def test_rollback_is_rejected(
    tmp_path: Path,
) -> None:
    recorder = _recorder(
        tmp_path
    )

    recorder.append(
        event_type="sandbox.started",
        execution_id="exec-1",
        data={},
    )

    old_ledger = (
        recorder.path.read_bytes()
    )

    recorder.append(
        event_type="sandbox.finished",
        execution_id="exec-1",
        data={},
    )

    # Restore the older valid ledger while leaving
    # the independently stored head checkpoint current.
    recorder.path.write_bytes(
        old_ledger
    )

    with pytest.raises(
        EvidenceIntegrityError,
        match="length",
    ):
        recorder.verify()

    print(
        "REAL_EVIDENCE_ROLLBACK_REJECTED_OK"
    )


def test_append_refuses_corrupt_existing_chain(
    tmp_path: Path,
) -> None:
    recorder = _recorder(
        tmp_path
    )

    recorder.append(
        event_type="sandbox.started",
        execution_id="exec-1",
        data={},
    )

    recorder.path.write_text(
        '{"broken":true}\n',
        encoding="utf-8",
    )

    with pytest.raises(
        EvidenceIntegrityError
    ):
        recorder.append(
            event_type="sandbox.finished",
            execution_id="exec-1",
            data={},
        )

    print(
        "REAL_EVIDENCE_CORRUPT_APPEND_REJECTED_OK"
    )


def test_missing_anchor_is_rejected(
    tmp_path: Path,
) -> None:
    recorder = _recorder(
        tmp_path
    )

    recorder.append(
        event_type="sandbox.started",
        execution_id="exec-1",
        data={},
    )

    recorder.anchor.path.unlink()

    with pytest.raises(
        EvidenceIntegrityError,
        match="without durable head anchor",
    ):
        recorder.verify()

    print(
        "REAL_EVIDENCE_MISSING_ANCHOR_REJECTED_OK"
    )


def test_real_kernel_resource_usage_evidence() -> None:
    from engine.sandbox.evidence import (
        resource_usage_evidence,
    )
    from engine.sandbox.lifecycle.timeout import (
        run_process,
    )

    outcome = run_process(
        (
            "/bin/sh",
            "-c",
            """
python3 - <<'INNER'
data = bytearray(16 * 1024 * 1024)

value = 0
for i in range(750000):
    value += i * i

print(len(data), value > 0)
INNER
""",
        ),
        timeout_seconds=10,
    )

    assert outcome.exit_code == 0

    usage = resource_usage_evidence(
        outcome
    )

    assert usage.user_cpu_seconds >= 0.0
    assert usage.system_cpu_seconds >= 0.0

    assert (
        usage.total_cpu_seconds
        == (
            usage.user_cpu_seconds
            + usage.system_cpu_seconds
        )
    )

    # Linux wait4() reports ru_maxrss in KiB.
    # The real child allocates 16 MiB, so this
    # must be a genuine positive kernel value.
    assert usage.max_rss_kb > 0

    assert (
        usage.voluntary_context_switches
        >= 0
    )

    assert (
        usage.involuntary_context_switches
        >= 0
    )

    print(
        "REAL_KERNEL_RESOURCE_USAGE_EVIDENCE_OK"
    )



def test_real_filesystem_evidence_diff(
    tmp_path: Path,
) -> None:
    from engine.sandbox.evidence import (
        diff_filesystems,
        snapshot_filesystem,
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    unchanged = workspace / "unchanged.txt"
    unchanged.write_text(
        "same\n",
        encoding="utf-8",
    )

    modified = workspace / "modified.txt"
    modified.write_text(
        "before\n",
        encoding="utf-8",
    )

    removed = workspace / "removed.txt"
    removed.write_text(
        "removed\n",
        encoding="utf-8",
    )

    link = workspace / "link"
    link.symlink_to(
        "unchanged.txt"
    )

    before = snapshot_filesystem(
        workspace
    )

    modified.write_text(
        "after\n",
        encoding="utf-8",
    )

    removed.unlink()

    added = workspace / "added.txt"
    added.write_text(
        "added\n",
        encoding="utf-8",
    )

    link.unlink()

    link.symlink_to(
        "modified.txt"
    )

    after = snapshot_filesystem(
        workspace
    )

    changes = diff_filesystems(
        before,
        after,
    )

    observed = {
        (
            change.path,
            change.change_type,
        )
        for change in changes
    }

    assert (
        "modified.txt",
        "modified",
    ) in observed

    assert (
        "removed.txt",
        "removed",
    ) in observed

    assert (
        "added.txt",
        "added",
    ) in observed

    assert (
        "link",
        "symlink_target_changed",
    ) in observed

    assert not any(
        change.path == "unchanged.txt"
        for change in changes
    )

    print(
        "REAL_FILESYSTEM_EVIDENCE_DIFF_OK"
    )



def test_real_execution_evidence_models(
    tmp_path: Path,
) -> None:
    from engine.sandbox.evidence import (
        process_outcome_evidence,
        request_evidence,
        result_evidence,
    )

    from engine.sandbox.lifecycle.timeout import (
        run_process,
    )

    from engine.sandbox.models import (
        IsolationClass,
        ResourceLimits,
        RuntimeKind,
        SandboxRequest,
        SandboxResult,
        TrustLevel,
        WorkloadType,
    )

    request = SandboxRequest(
        workload_type=WorkloadType.TEST,
        trust_level=TrustLevel.TRUSTED,
        command=(
            "/bin/sh",
            "-c",
            "printf 'EVIDENCE_OK\\n'",
        ),
        working_directory=tmp_path,
        network_enabled=False,
        writable_workspace=True,
        environment={
            "SECRET_TOKEN": "must-not-be-recorded",
            "SAFE_NAME": "value",
        },
        limits=ResourceLimits(
            cpu_count=1.0,
            memory_mb=256,
            timeout_seconds=5,
            pids=16,
        ),
    )

    request_record = request_evidence(
        request
    )

    assert (
        request_record.environment_keys
        == (
            "SAFE_NAME",
            "SECRET_TOKEN",
        )
    )

    assert (
        "must-not-be-recorded"
        not in str(
            request_record.to_dict()
        )
    )

    outcome = run_process(
        request.command,
        timeout_seconds=5,
        cwd=tmp_path,
    )

    outcome_record = (
        process_outcome_evidence(
            outcome
        )
    )

    assert outcome_record.exit_code == 0

    assert (
        outcome_record.stdout
        == "EVIDENCE_OK\n"
    )

    result = SandboxResult(
        runtime_kind=RuntimeKind.PODMAN,
        isolation_class=IsolationClass.HOST_OS,
        command=tuple(
            request.command
        ),
        exit_code=outcome.exit_code,
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        timed_out=outcome.timed_out,
        duration_seconds=(
            outcome.duration_seconds
        ),
    )

    result_record = result_evidence(
        result
    )

    assert (
        result_record.runtime_kind
        == "podman"
    )

    assert (
        result_record.isolation_class
        == "host_os"
    )

    print(
        "REAL_EXECUTION_EVIDENCE_MODELS_OK"
    )
