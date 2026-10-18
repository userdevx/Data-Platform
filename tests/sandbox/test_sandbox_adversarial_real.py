from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from engine.sandbox.evidence import (
    EvidenceIntegrityError,
    EvidenceRecorder,
)
from engine.sandbox.lifecycle import (
    ExecutionLifecycle,
    ExecutionState,
    LifecycleError,
)
from engine.sandbox.policy.network import NetworkPolicy
from engine.sandbox.registry import (
    ArtifactDescriptor,
    ArtifactTrustError,
    RuntimeImageRegistry,
)


def test_default_network_fail_closed() -> None:
    policy = NetworkPolicy()

    assert not policy.network_enabled
    assert not policy.permits_ip("127.0.0.1", 1)
    assert not policy.permits_ip("1.1.1.1", 443)


def test_unknown_artifact_fails_closed() -> None:
    registry = RuntimeImageRegistry()

    with pytest.raises(Exception):
        registry.verify_artifact("does-not-exist")


def test_modified_artifact_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "image"
    artifact.write_bytes(b"original")

    expected = hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()

    registry = RuntimeImageRegistry()
    registry.register_artifact(
        ArtifactDescriptor(
            name="image",
            path=artifact,
            sha256=expected,
        )
    )

    artifact.write_bytes(b"modified")

    with pytest.raises(ArtifactTrustError):
        registry.verify_artifact("image")


def test_evidence_tampering_fails_closed(
    tmp_path: Path,
) -> None:
    import json

    path = tmp_path / "evidence.jsonl"

    recorder = EvidenceRecorder(path)

    recorder.append(
        event_type="test",
        execution_id="exec",
        data={"ok": True},
    )

    lines = path.read_text(
        encoding="utf-8",
    ).splitlines()

    assert len(lines) == 1

    record = json.loads(
        lines[0]
    )

    assert record["data"]["ok"] is True

    record["data"]["ok"] = False

    path.write_text(
        json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        EvidenceIntegrityError
    ):
        recorder.verify()

    print(
        "ADVERSARIAL_EVIDENCE_TAMPER_FAIL_CLOSED_OK"
    )


def test_illegal_lifecycle_transition_fails_closed() -> None:
    lifecycle = ExecutionLifecycle()
    record = lifecycle.create()

    with pytest.raises(LifecycleError):
        lifecycle.transition(
            record,
            ExecutionState.FINISHED,
        )
