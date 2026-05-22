import json
import os
import socket
import uuid
from datetime import datetime, timezone


JOB_DIR = "data/jobs"

SUCCESSFUL_JOBS_FILE = f"{JOB_DIR}/successful_jobs.json"
FAILED_JOBS_FILE = f"{JOB_DIR}/failed_jobs.json"
RETRY_JOBS_FILE = f"{JOB_DIR}/retry_jobs.json"
DEAD_JOBS_FILE = f"{JOB_DIR}/dead_jobs.json"


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def get_host():
    return socket.gethostname()


def ensure_job_files():
    os.makedirs(JOB_DIR, exist_ok=True)

    for file_path in [
        SUCCESSFUL_JOBS_FILE,
        FAILED_JOBS_FILE,
        RETRY_JOBS_FILE,
        DEAD_JOBS_FILE,
    ]:
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump([], file, indent=2)


def load_jobs(file_path):
    ensure_job_files()

    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read().strip()

        if not content:
            return []

        return json.loads(content)


def save_jobs(file_path, jobs):
    ensure_job_files()

    temp_file = f"{file_path}.tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(jobs, file, indent=2)

    os.replace(temp_file, file_path)


def create_job_run(
    job_id,
    pipeline_name,
    task_name,
    ran_by="system",
    max_attempts=3,
):
    now = current_timestamp()

    return {
        "run_id": str(uuid.uuid4()),
        "job_id": job_id,
        "pipeline_name": pipeline_name,
        "task_name": task_name,
        "status": "running",
        "ran_by": ran_by,
        "worker_id": get_host(),
        "host": get_host(),
        "started_at": now,
        "finished_at": None,
        "duration_ms": None,
        "attempt": 1,
        "max_attempts": max_attempts,
        "can_rerun": True,
        "error_type": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }


def calculate_duration_ms(started_at, finished_at):
    start = datetime.fromisoformat(started_at)
    finish = datetime.fromisoformat(finished_at)
    return int((finish - start).total_seconds() * 1000)


def complete_job(job_run):
    now = current_timestamp()

    job_run["status"] = "success"
    job_run["finished_at"] = now
    job_run["duration_ms"] = calculate_duration_ms(
        job_run["started_at"],
        job_run["finished_at"],
    )
    job_run["can_rerun"] = False
    job_run["updated_at"] = now

    jobs = load_jobs(SUCCESSFUL_JOBS_FILE)
    jobs.append(job_run)
    save_jobs(SUCCESSFUL_JOBS_FILE, jobs)

    return job_run


def fail_job(job_run, error):
    now = current_timestamp()

    job_run["status"] = "failed"
    job_run["finished_at"] = now
    job_run["duration_ms"] = calculate_duration_ms(
        job_run["started_at"],
        job_run["finished_at"],
    )
    job_run["error_type"] = type(error).__name__
    job_run["error_message"] = str(error)
    job_run["updated_at"] = now

    failed_jobs = load_jobs(FAILED_JOBS_FILE)
    failed_jobs.append(job_run)
    save_jobs(FAILED_JOBS_FILE, failed_jobs)

    if job_run["attempt"] < job_run["max_attempts"]:
        retry_job = dict(job_run)
        retry_job["status"] = "retrying"
        retry_job["attempt"] += 1
        retry_job["can_rerun"] = True
        retry_job["updated_at"] = current_timestamp()

        retry_jobs = load_jobs(RETRY_JOBS_FILE)
        retry_jobs.append(retry_job)
        save_jobs(RETRY_JOBS_FILE, retry_jobs)
    else:
        dead_job = dict(job_run)
        dead_job["status"] = "dead"
        dead_job["can_rerun"] = False
        dead_job["updated_at"] = current_timestamp()

        dead_jobs = load_jobs(DEAD_JOBS_FILE)
        dead_jobs.append(dead_job)
        save_jobs(DEAD_JOBS_FILE, dead_jobs)

    return job_run


def get_successful_jobs():
    return load_jobs(SUCCESSFUL_JOBS_FILE)


def get_failed_jobs():
    return load_jobs(FAILED_JOBS_FILE)


def get_retry_jobs():
    return load_jobs(RETRY_JOBS_FILE)


def get_dead_jobs():
    return load_jobs(DEAD_JOBS_FILE)
