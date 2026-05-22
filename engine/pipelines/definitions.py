from datetime import datetime, timezone


VALID_PIPELINE_STATUSES = [
    "active",
    "paused",
    "deprecated",
    "sunset",
]


VALID_TASK_TYPES = [
    "extract",
    "transform",
    "load",
    "quality_check",
    "alert",
    "export",
]


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def create_task(
    task_name,
    task_type,
    depends_on=None,
    retries=3,
    timeout_seconds=60,
):
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(f"Invalid task_type: {task_type}")

    return {
        "task_name": task_name,
        "task_type": task_type,
        "depends_on": depends_on or [],
        "retries": retries,
        "timeout_seconds": timeout_seconds,
    }


def create_pipeline_definition(
    pipeline_name,
    description,
    tasks,
    schedule=None,
    owner="system",
    status="active",
    metadata=None,
):
    if status not in VALID_PIPELINE_STATUSES:
        raise ValueError(f"Invalid pipeline status: {status}")

    return {
        "pipeline_name": pipeline_name,
        "description": description,
        "status": status,
        "owner": owner,
        "schedule": schedule,
        "tasks": tasks,
        "metadata": metadata or {},
        "created_at": current_timestamp(),
        "updated_at": current_timestamp(),
    }
