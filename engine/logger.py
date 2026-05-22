import os
from datetime import datetime, timezone


LOG_DIR = "logs"
ENGINE_LOG = "logs/engine.log"
ERROR_LOG = "logs/errors.log"


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def write_log(file_path, level, event, message):
    ensure_log_dir()

    log_line = (
        f"{current_timestamp()} | "
        f"{level} | "
        f"{event} | "
        f"{message}\n"
    )

    with open(file_path, "a", encoding="utf-8") as file:
        file.write(log_line)


def log_info(event, message):
    write_log(ENGINE_LOG, "INFO", event, message)


def log_error(event, message):
    write_log(ERROR_LOG, "ERROR", event, message)
