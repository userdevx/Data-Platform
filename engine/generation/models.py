"""Generation job state, profile, and Data Engine record envelopes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


IMAGE_GENERATION = "image_generation"
IMAGE_TO_IMAGE = "image_to_image"

RECORD_SOURCE = "intelligence_runtime"

CATEGORY_JOB_STATE = "job_state"
CATEGORY_ARTIFACT = "generation_artifact"

DATA_TYPE_JOB_STATUS = "generation_job_status"
DATA_TYPE_IMAGE_ARTIFACT = "image_artifact"

UNIT_STATUS = "status"
UNIT_ARTIFACT = "artifact"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


TERMINAL_STATES = frozenset(
    {
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.CANCELLED,
        JobState.REJECTED,
    }
)


class FailureReason(str, Enum):
    PIPELINE_LOAD = "pipeline_load"
    GENERATION = "generation"
    VALIDATION = "validation"
    HEARTBEAT_LOST = "heartbeat_lost"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    NO_CAPABLE_MODEL = "no_capable_model"
    INSUFFICIENT_RESOURCES = "insufficient_resources"
    WORKER_ERROR = "worker_error"
    USER = "user"
    SHUTDOWN = "shutdown"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GenerationProfile:
    steps: int = 8
    width: int = 256
    height: int = 256
    seed: int = 17
    guidance_scale: float = 7.5
    negative_prompt: str = ""
    scheduler: str = ""
    vae_tiling: bool = True
    attention_slicing: bool = True
    strength: float | None = None
    name: str = "safe_baseline"

    def __post_init__(self) -> None:
        if not 1 <= self.steps <= 150:
            raise ValueError("steps must be between 1 and 150.")

        for axis, value in (("width", self.width), ("height", self.height)):
            if not 64 <= value <= 2048:
                raise ValueError(f"{axis} must be between 64 and 2048.")

            if value % 8:
                raise ValueError(f"{axis} must be a multiple of 8.")

        if not 0 <= self.seed <= 2 ** 31 - 1:
            raise ValueError("seed must be a non-negative 31-bit integer.")

        if not 0.0 <= self.guidance_scale <= 20.0:
            raise ValueError("guidance_scale must be between 0.0 and 20.0.")

        if self.strength is not None and not 0.0 < self.strength <= 1.0:
            raise ValueError("strength must be within (0.0, 1.0].")

        if self.strength is not None:
            effective = int(self.steps * self.strength)

            if effective < 3:
                raise ValueError(
                    "steps x strength yields fewer than three effective "
                    f"denoising steps ({effective}); raise steps or strength."
                )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


SAFE_BASELINE = GenerationProfile()


@dataclass
class GenerationJob:
    job_id: str
    request_id: str
    capability: str
    prompt: str
    profile: GenerationProfile
    budget: dict[str, Any]
    hardware: dict[str, Any]
    idempotency_key: str
    model_id: str = ""
    state: JobState = JobState.QUEUED
    reason: str | None = None
    artifact_id: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    ended_at: str | None = None
    heartbeat_at: str | None = None
    memory_peak_bytes: int | None = None
    duration_ms: int | None = None

    def transition(
        self,
        state: JobState,
        *,
        reason: FailureReason | str | None = None,
        **updates: Any,
    ) -> "GenerationJob":
        if self.state in TERMINAL_STATES:
            raise ValueError(
                f"Job {self.job_id} is already terminal ({self.state.value})."
            )

        if isinstance(reason, FailureReason):
            reason = reason.value

        changes: dict[str, Any] = {"state": state, "reason": reason}
        changes.update(updates)

        if state is JobState.RUNNING and self.started_at is None:
            changes.setdefault("started_at", utc_now())

        if state in TERMINAL_STATES:
            changes.setdefault("ended_at", utc_now())

        return replace(self, **changes)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["profile"] = self.profile.as_dict()
        return payload


def build_idempotency_key(
    *,
    capability: str,
    prompt: str,
    model_id: str,
    profile: GenerationProfile,
    arguments: dict[str, Any] | None = None,
) -> str:
    payload = {
        "capability": capability,
        "prompt": prompt,
        "model_id": model_id,
        "profile": profile.as_dict(),
        "arguments": arguments or {},
    }

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def new_job(
    *,
    capability: str,
    prompt: str,
    profile: GenerationProfile,
    budget: dict[str, Any],
    hardware: dict[str, Any],
    request_id: str = "",
    model_id: str = "",
    arguments: dict[str, Any] | None = None,
) -> GenerationJob:
    arguments = dict(arguments or {})

    return GenerationJob(
        job_id=str(uuid4()),
        request_id=request_id or str(uuid4()),
        capability=capability,
        prompt=prompt,
        profile=profile,
        budget=budget,
        hardware=hardware,
        model_id=model_id,
        arguments=arguments,
        idempotency_key=build_idempotency_key(
            capability=capability,
            prompt=prompt,
            model_id=model_id,
            profile=profile,
            arguments=arguments,
        ),
    )


def job_state_record(job: GenerationJob) -> dict[str, Any]:
    return {
        "source": RECORD_SOURCE,
        "category": CATEGORY_JOB_STATE,
        "data_type": DATA_TYPE_JOB_STATUS,
        "value": {
            "job_id": job.job_id,
            "request_id": job.request_id,
            "idempotency_key": job.idempotency_key,
            "capability": job.capability,
            "model_id": job.model_id,
            "state": job.state.value,
            "reason": job.reason,
            "artifact_id": job.artifact_id,
            "arguments": job.arguments,
            "profile": job.profile.as_dict(),
            "budget": job.budget,
            "hardware": job.hardware,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "ended_at": job.ended_at,
            "heartbeat_at": job.heartbeat_at,
            "resources": {
                "memory_peak_bytes": job.memory_peak_bytes,
                "duration_ms": job.duration_ms,
            },
        },
        "unit": UNIT_STATUS,
    }


def artifact_record(
    job: GenerationJob,
    *,
    artifact_id: str,
    relative_path: str,
    sha256: str,
    mime_type: str,
    validation: dict[str, Any],
    pipeline_class: str = "",
    runtime_format: str = "",
    device: str = "",
    dtype: str = "",
    prompt_original: str | None = None,
    prompt_prepared_by: str = "",
    source_artifact_sha256: str = "",
    source_dimensions: list[int] | None = None,
    working_dimensions: list[int] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "artifact_id": artifact_id,
        "job_id": job.job_id,
        "request_id": job.request_id,
        "capability": job.capability,
        "model_id": job.model_id,
        "relative_path": relative_path,
        "sha256": sha256,
        "mime_type": mime_type,
        "prompt_original": prompt_original if prompt_original is not None else job.prompt,
        "prompt_prepared": job.prompt,
        "prompt_prepared_by": prompt_prepared_by,
        "prompt_hash": hashlib.sha256(job.prompt.encode("utf-8")).hexdigest(),
        "profile": job.profile.as_dict(),
        "budget": job.budget,
        "pipeline_class": pipeline_class,
        "runtime_format": runtime_format,
        "device": device,
        "dtype": dtype,
        "validation": validation,
        "resources": {
            "memory_peak_bytes": job.memory_peak_bytes,
            "duration_ms": job.duration_ms,
        },
    }

    if source_artifact_sha256:
        value["source_artifact_sha256"] = source_artifact_sha256

    if source_dimensions:
        value["source_dimensions"] = list(source_dimensions)

    if working_dimensions:
        value["working_dimensions"] = list(working_dimensions)

    return {
        "source": RECORD_SOURCE,
        "category": CATEGORY_ARTIFACT,
        "data_type": DATA_TYPE_IMAGE_ARTIFACT,
        "value": value,
        "unit": UNIT_ARTIFACT,
    }
