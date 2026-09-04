"""Generation integration boundaries.

Phase 1 deliberately leaves the real Data Engine record-store binding
and the worker CLI command binding unresolved. Phase 2 inspects the
actual Data Engine and worker CLI before implementing either boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .models import GenerationJob
from .store import JobRecordStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_job_record_store() -> JobRecordStore:
    raise NotImplementedError(
        "Phase 2 must bind GenerationJob persistence to the real Data Engine."
    )


def build_worker_command(job: GenerationJob) -> Sequence[str]:
    raise NotImplementedError(
        "Phase 2 must bind GenerationJob execution to the verified worker CLI."
    )
