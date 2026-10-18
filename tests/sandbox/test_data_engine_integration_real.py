from __future__ import annotations

from engine.sandbox.data_engine import (
    CANONICAL_FIELDS,
    sandbox_result_record,
)


def test_sandbox_record_uses_exact_data_engine_schema() -> None:
    record = sandbox_result_record(
        execution_id="exec-1",
        runtime_kind="firecracker",
        isolation_class="hardware",
        exit_code=0,
        timed_out=False,
        duration_seconds=1.25,
        stdout="ok\n",
        stderr="",
    )

    assert tuple(record) == CANONICAL_FIELDS

    assert tuple(record) == (
        "source",
        "category",
        "data_type",
        "value",
        "unit",
    )

    assert "sensor_type" not in record
    assert record["source"] == "sandbox"
    assert record["data_type"] == "sandbox_result"
