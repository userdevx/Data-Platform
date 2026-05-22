import json
import os
import shutil
from datetime import datetime, timezone


DATA_FILE = "data/records.json"
BACKUP_FILE = "data/records.json.backup"

JOB_DIR = "data/jobs"
LOG_DIR = "logs"

JOB_FILES = [
    "successful_jobs.json",
    "failed_jobs.json",
    "retry_jobs.json",
    "dead_jobs.json",
]


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def check_json_file(file_path):
    if not os.path.exists(file_path):
        return False, "missing"

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read().strip()

            if not content:
                return False, "empty"

            json.loads(content)

        return True, "valid"

    except json.JSONDecodeError:
        return False, "invalid_json"


def ensure_directory(directory_path):
    os.makedirs(directory_path, exist_ok=True)


def ensure_json_list_file(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump([], file, indent=2)


def recover_data_file():
    valid, status = check_json_file(DATA_FILE)

    if valid:
        return {
            "file": DATA_FILE,
            "status": "valid",
            "action": "none",
        }

    backup_valid, backup_status = check_json_file(BACKUP_FILE)

    if backup_valid:
        shutil.copyfile(BACKUP_FILE, DATA_FILE)

        return {
            "file": DATA_FILE,
            "status": status,
            "backup_status": backup_status,
            "action": "restored_from_backup",
        }

    ensure_directory("data")
    ensure_json_list_file(DATA_FILE)

    return {
        "file": DATA_FILE,
        "status": status,
        "backup_status": backup_status,
        "action": "created_empty_data_file",
    }


def recover_job_files():
    ensure_directory(JOB_DIR)

    results = []

    for job_file in JOB_FILES:
        file_path = os.path.join(JOB_DIR, job_file)
        valid, status = check_json_file(file_path)

        if valid:
            action = "none"
        else:
            ensure_json_list_file(file_path)
            action = "created_empty_job_file"

        results.append({
            "file": file_path,
            "status": status,
            "action": action,
        })

    return results


def recover_log_directory():
    ensure_directory(LOG_DIR)

    return {
        "directory": LOG_DIR,
        "status": "ready",
        "action": "ensured_directory_exists",
    }


def run_recovery_check():
    report = {
        "checked_at": current_timestamp(),
        "data": recover_data_file(),
        "jobs": recover_job_files(),
        "logs": recover_log_directory(),
        "status": "recovery_check_complete",
    }

    return report
