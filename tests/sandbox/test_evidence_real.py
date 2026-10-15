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
