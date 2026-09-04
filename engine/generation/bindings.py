"""Generation integration boundaries.

Generation lifecycle persistence uses the existing Data Engine write and
query paths. Heavy worker execution remains deliberately unresolved until
the actual generation worker CLI is inspected and verified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from engine.backend import get_backend
from engine.data_engine.record_writer import DataEngineRecordWriter
from engine.model_development.runtime import resolve_base_model
from engine.query import QueryService

from .models import IMAGE_GENERATION, GenerationJob
from .store import DataEngineJobRecordStore, JobRecordStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PYTHON = (
    PROJECT_ROOT
    / "venv-training"
    / "bin"
    / "python"
)

WORKER_MODULE = (
    "engine.model_development.worker_cli"
)


def _write_generation_record(
    writer: DataEngineRecordWriter,
    record: dict[str, Any],
) -> None:
    """Write one normalized generation envelope through the Data Engine."""

    if not isinstance(record, dict):
        raise TypeError(
            "Generation record must be a dictionary."
        )

    required_fields = (
        "source",
        "category",
        "data_type",
        "value",
        "unit",
    )

    missing = [
        field
        for field in required_fields
        if field not in record
    ]

    if missing:
        raise ValueError(
            "Generation record is missing fields: "
            f"{missing}"
        )

    writer.write(
        source=record["source"],
        category=record["category"],
        data_type=record["data_type"],
        value=record["value"],
        unit=record["unit"],
        metadata=record.get("metadata"),
    )


def _query_generation_records(
    query_service: QueryService,
    category: str,
    data_type: str,
) -> list[dict[str, Any]]:
    """Read generation records from the authoritative Data Engine."""

    records = query_service.get_all_records()

    return [
        record
        for record in records
        if isinstance(record, dict)
        and record.get("category") == category
        and record.get("data_type") == data_type
    ]


def build_job_record_store(
    *,
    query_service: QueryService | None = None,
) -> JobRecordStore:
    """Build the GenerationJob store on the real Data Engine boundary.

    A supplied QueryService is primarily useful for isolated integration
    testing. Normal runtime construction uses the configured Data Engine
    backend.
    """

    service = (
        query_service
        if query_service is not None
        else QueryService(
            get_backend()
        )
    )

    writer = DataEngineRecordWriter(
        query_service=service,
    )

    return DataEngineJobRecordStore(
        append_record=lambda record: (
            _write_generation_record(
                writer,
                record,
            )
        ),
        query_records=lambda category, data_type: (
            _query_generation_records(
                service,
                category,
                data_type,
            )
        ),
    )


def build_worker_command(
    job: GenerationJob,
) -> Sequence[str]:
    """Build the verified local image-generation worker command."""

    if not MODEL_PYTHON.is_file():
        raise ValueError(
            "The verified local model execution environment "
            "is unavailable."
        )

    if job.capability != IMAGE_GENERATION:
        raise ValueError(
            "The bounded generation worker currently supports "
            "image_generation only."
        )

    descriptor = resolve_base_model(
        job.model_id
    )

    if descriptor.capability != IMAGE_GENERATION:
        raise ValueError(
            "The selected local model does not support "
            "image_generation."
        )

    if job.profile.strength is not None:
        raise ValueError(
            "Image-to-image strength is not connected to the "
            "bounded worker yet."
        )

    if job.profile.scheduler.strip():
        raise ValueError(
            "Explicit scheduler selection is not connected to "
            "the bounded worker yet."
        )

    command: list[str] = [
        str(MODEL_PYTHON),
        "-m",
        WORKER_MODULE,
        "execute",
        "--model",
        descriptor.name,
        "--prompt",
        job.prompt,
        "--steps",
        str(job.profile.steps),
        "--width",
        str(job.profile.width),
        "--height",
        str(job.profile.height),
        "--seed",
        str(job.profile.seed),
        "--guidance-scale",
        str(job.profile.guidance_scale),
        "--negative-prompt",
        job.profile.negative_prompt,
    ]

    command.append(
        "--vae-tiling"
        if job.profile.vae_tiling
        else "--no-vae-tiling"
    )

    command.append(
        "--attention-slicing"
        if job.profile.attention_slicing
        else "--no-attention-slicing"
    )

    return command
