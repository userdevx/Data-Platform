from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


CANONICAL_FIELDS = (
    "source",
    "category",
    "data_type",
    "value",
    "unit",
)


def sandbox_result_record(
    *,
    execution_id: str,
    runtime_kind: str,
    isolation_class: str,
    exit_code: int,
    timed_out: bool,
    duration_seconds: float,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    record = {
        "source": "sandbox",
        "category": "execution",
        "data_type": "sandbox_result",
        "value": {
            "execution_id": execution_id,
            "runtime_kind": runtime_kind,
            "isolation_class": isolation_class,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": duration_seconds,
            "stdout": stdout,
            "stderr": stderr,
        },
        "unit": None,
    }

    if tuple(record) != CANONICAL_FIELDS:
        raise RuntimeError(
            "sandbox Data Engine record schema changed"
        )

    return record


@dataclass
class DataEngineSandboxRecorder:
    """Dependency-injected Data Engine write boundary.

    The caller supplies the real Data Engine writer. This module does not
    introduce SQLite or another application datastore.
    """

    writer: Callable[[dict[str, Any]], Any]

    def record_result(
        self,
        *,
        execution_id: str,
        result: object,
    ) -> Any:
        runtime_kind = getattr(
            getattr(result, "runtime_kind"),
            "value",
            str(getattr(result, "runtime_kind")),
        )

        isolation_class = getattr(
            getattr(result, "isolation_class"),
            "value",
            str(getattr(result, "isolation_class")),
        )

        record = sandbox_result_record(
            execution_id=execution_id,
            runtime_kind=runtime_kind,
            isolation_class=isolation_class,
            exit_code=int(
                getattr(result, "exit_code")
            ),
            timed_out=bool(
                getattr(result, "timed_out")
            ),
            duration_seconds=float(
                getattr(result, "duration_seconds")
            ),
            stdout=str(
                getattr(result, "stdout")
            ),
            stderr=str(
                getattr(result, "stderr")
            ),
        )

        return self.writer(record)
