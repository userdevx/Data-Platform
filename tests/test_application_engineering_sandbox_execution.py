from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from engine.application_engineering.execution_policy import (
    BuilderExecutionPolicy,
    make_builder_manager,
)
from engine.application_engineering.models import ValidationStep
from engine.application_engineering.runtime import ApplicationEngineeringRuntime
from engine.data_engine.record_writer import DataEngineRecordWriter
from engine.query import QueryService
from engine.storage.json_backend import LocalJsonStorageBackend


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def real_environment(*, image_id: str | None = None):
    with TemporaryDirectory(prefix="dataworc-6b1-real-") as directory:
        base = Path(directory)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o755)

        evidence_file = base / "evidence.json"
        policy = BuilderExecutionPolicy.load(ROOT)

        if image_id is not None:
            policy = replace(policy, image_id=image_id)

        writer = DataEngineRecordWriter(
            query_service=QueryService(
                LocalJsonStorageBackend(str(evidence_file))
            )
        )

        runtime = ApplicationEngineeringRuntime(
            project_root=ROOT,
            workspace=workspace,
            application_id="6b1-real-test",
            requirement_id="6b1-real-test",
            writer=writer,
            execution_policy=policy,
            sandbox_manager=make_builder_manager(policy.image_id),
        )

        yield runtime, workspace, evidence_file, policy


def persisted_record(evidence_file: Path):
    # Reopen actual storage with a fresh backend and query service.
    query = QueryService(
        LocalJsonStorageBackend(str(evidence_file))
    )
    records = query.get_all_records()

    assert len(records) == 1, records
    record = records[0]

    for field in (
        "source", "category", "data_type", "value", "unit"
    ):
        assert field in record

    assert "sensor_type" not in record
    assert record["source"] == "application_engineering"
    assert record["category"] == "application_engineering"
    assert record["unit"] == "record"

    return record


def execute_script(runtime, workspace, name, source):
    (workspace / name).write_text(source, encoding="utf-8")
    return runtime._execute_step(
        ValidationStep(
            description="run: real integration",
            command=f"python3 {name}",
        )
    )


def test_real_success_and_persistent_evidence():
    with real_environment() as (runtime, workspace, evidence, policy):
        result = execute_script(
            runtime,
            workspace,
            "success.py",
            "print('DATAWORC_REAL_SUCCESS')\n",
        )

        assert result["success"] is True, result
        assert result["exit_code"] == 0
        assert result["runtime_kind"] == "gvisor"
        assert result["isolation_class"] == "kernel_emulation"
        assert result["timed_out"] is False
        assert result["image_id"] == policy.image_id
        assert "DATAWORC_REAL_SUCCESS" in result["stdout"]

        record = persisted_record(evidence)
        assert record["data_type"] == "runtime_verification"
        assert record["value"]["execution_id"] == result["execution_id"]
        assert record["value"]["stdout"] == result["stdout"]
        assert record["value"]["success"] is True


def test_real_nonzero_exit_and_persistent_evidence():
    with real_environment() as (runtime, workspace, evidence, _):
        result = execute_script(
            runtime,
            workspace,
            "failure.py",
            "import sys\n"
            "print('EXPECTED_FAILURE')\n"
            "sys.exit(17)\n",
        )

        assert result["success"] is False
        assert result["exit_code"] == 17
        assert result["runtime_kind"] == "gvisor"
        assert result["timed_out"] is False
        assert "EXPECTED_FAILURE" in result["stdout"]

        record = persisted_record(evidence)
        assert record["value"]["exit_code"] == 17
        assert record["value"]["success"] is False


def test_real_missing_builder_fails_closed():
    missing_image = "sha256:" + "0" * 64

    with real_environment(image_id=missing_image) as (
        runtime, workspace, evidence, _
    ):
        result = execute_script(
            runtime,
            workspace,
            "missing.py",
            "print('MUST_NOT_EXECUTE')\n",
        )

        assert result["success"] is False
        assert result["exit_code"] is None
        assert result["runtime_kind"] is None
        assert result["image_id"] == missing_image
        assert "GVisorRuntimeUnavailable" in result["stderr"]
        assert "MUST_NOT_EXECUTE" not in result["stdout"]

        record = persisted_record(evidence)
        assert record["value"]["success"] is False
        assert record["value"]["runtime_kind"] is None


def test_unsupported_command_fails_closed_and_persists():
    with real_environment() as (runtime, _, evidence, _):
        result = runtime._execute_step(
            ValidationStep(
                description="run: rejected command",
                command="npm test",
            )
        )

        assert result["success"] is False
        assert result["exit_code"] is None
        assert result["runtime_kind"] is None
        assert "not verified" in result["stderr"]

        record = persisted_record(evidence)
        assert record["value"]["success"] is False


def test_real_workspace_write_denied():
    with real_environment() as (runtime, workspace, evidence, _):
        result = execute_script(
            runtime,
            workspace,
            "write_check.py",
            "from pathlib import Path\n"
            "try:\n"
            "    Path('/workspace/probe.txt').write_text('bad')\n"
            "except OSError:\n"
            "    print('WORKSPACE_WRITE_DENIED')\n"
            "else:\n"
            "    raise SystemExit('WORKSPACE_WRITE_ALLOWED')\n",
        )

        assert result["success"] is True, result
        assert result["runtime_kind"] == "gvisor"
        assert "WORKSPACE_WRITE_DENIED" in result["stdout"]
        assert not (workspace / "probe.txt").exists()

        record = persisted_record(evidence)
        assert record["value"]["success"] is True


def test_real_timeout_and_persistent_evidence():
    # Real production timeout: 120 seconds. No simulation.
    with real_environment() as (runtime, workspace, evidence, policy):
        result = execute_script(
            runtime,
            workspace,
            "slow.py",
            "import time\n"
            "print('TIMEOUT_STARTED', flush=True)\n"
            "time.sleep(180)\n"
            "print('UNEXPECTED_COMPLETION', flush=True)\n",
        )

        assert result["success"] is False, result
        assert result["timed_out"] is True
        assert result["exit_code"] == 124
        assert result["runtime_kind"] == "gvisor"
        assert result["isolation_class"] == "kernel_emulation"
        assert result["duration_seconds"] >= 120
        assert result["image_id"] == policy.image_id
        assert "UNEXPECTED_COMPLETION" not in result["stdout"]

        record = persisted_record(evidence)
        value = record["value"]

        assert value["timed_out"] is True
        assert value["success"] is False
        assert value["exit_code"] == 124
        assert value["execution_id"] == result["execution_id"]
