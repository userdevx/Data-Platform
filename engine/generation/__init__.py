"""Resource-protected generation jobs for the Data Platform."""

from __future__ import annotations

from .budget import (
    ExecutionBudget,
    HardwareSnapshot,
    InsufficientResourcesError,
    current_budget,
    derive_budget,
    detect_hardware,
)
from .models import (
    IMAGE_GENERATION,
    IMAGE_TO_IMAGE,
    SAFE_BASELINE,
    FailureReason,
    GenerationJob,
    GenerationProfile,
    JobState,
    TERMINAL_STATES,
    artifact_record,
    build_idempotency_key,
    job_state_record,
    new_job,
)
from .service import GenerationJobService, job_from_record
from .store import (
    DataEngineJobRecordStore,
    InMemoryJobRecordStore,
    JobRecordStore,
)

__all__ = [
    "DataEngineJobRecordStore",
    "ExecutionBudget",
    "FailureReason",
    "GenerationJob",
    "GenerationJobService",
    "GenerationProfile",
    "HardwareSnapshot",
    "IMAGE_GENERATION",
    "IMAGE_TO_IMAGE",
    "InMemoryJobRecordStore",
    "InsufficientResourcesError",
    "JobRecordStore",
    "JobState",
    "SAFE_BASELINE",
    "TERMINAL_STATES",
    "artifact_record",
    "build_idempotency_key",
    "current_budget",
    "derive_budget",
    "detect_hardware",
    "job_from_record",
    "job_state_record",
    "new_job",
]
