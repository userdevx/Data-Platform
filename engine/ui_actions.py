from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DATA_DIR = Path("data")
DATA_LAKE_DIR = Path("data_lake")
LOG_DIR = Path("logs")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def action_response(
    action: str,
    status: str,
    message: str,
    rows: list[dict[str, Any]] | None = None,
    data: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "action": action,
        "status": status,
        "message": message,
        "rows": rows or [],
        "data": data or {},
        "error": error,
        "updated_at": now_utc(),
    }


def ensure_runtime_folders() -> None:
    for path in [
        DATA_DIR,
        DATA_DIR / "imports",
        DATA_DIR / "databases",
        DATA_DIR / "exports",
        DATA_DIR / "jobs",
        DATA_LAKE_DIR / "raw",
        DATA_LAKE_DIR / "bronze",
        DATA_LAKE_DIR / "silver",
        DATA_LAKE_DIR / "gold",
        LOG_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


def count_jsonl_records(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0
    for file_path in path.rglob("*.jsonl"):
        with file_path.open("r", encoding="utf-8") as file:
            total += sum(1 for line in file if line.strip())

    return total


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0

    if path.is_file():
        return path.stat().st_size

    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024, 1)} KB"
    if size < 1024 * 1024 * 1024:
        return f"{round(size / 1024 / 1024, 1)} MB"
    return f"{round(size / 1024 / 1024 / 1024, 2)} GB"


def safe_database_name(name: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in name.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned


def workspace_refresh() -> dict[str, Any]:
    ensure_runtime_folders()

    raw_records = count_jsonl_records(DATA_LAKE_DIR / "raw")
    bronze_records = count_jsonl_records(DATA_LAKE_DIR / "bronze")
    silver_records = count_jsonl_records(DATA_LAKE_DIR / "silver")
    gold_records = count_jsonl_records(DATA_LAKE_DIR / "gold")
    database_count = len([path for path in (DATA_DIR / "databases").glob("*") if path.is_dir()])
    storage_used = format_bytes(folder_size(DATA_DIR))

    return action_response(
        action="workspace_refresh",
        status="success",
        message="Workspace loaded.",
        rows=[
            {"metric": "raw_records", "value": raw_records},
            {"metric": "bronze_records", "value": bronze_records},
            {"metric": "silver_records", "value": silver_records},
            {"metric": "gold_records", "value": gold_records},
            {"metric": "databases", "value": database_count},
            {"metric": "storage_used", "value": storage_used},
        ],
        data={
            "connected_sources": count_jsonl_records(DATA_DIR / "sources.jsonl"),
            "raw_records": raw_records,
            "databases": database_count,
            "storage_used": storage_used,
            "pipeline_status": {
                "raw_to_bronze": "ready" if raw_records else "waiting",
                "bronze_to_silver": "ready" if bronze_records else "waiting",
                "silver_to_gold": "ready" if silver_records else "waiting",
            },
        },
    )


def data_setup_ready() -> dict[str, Any]:
    ensure_runtime_folders()

    return action_response(
        action="data_setup_ready",
        status="success",
        message="Data setup ready.",
        rows=[
            {"field": "selected_file", "value": ""},
            {"field": "database_name", "value": ""},
            {"field": "data_drive", "value": str(DATA_DIR.resolve())},
            {"field": "database_location", "value": str((DATA_DIR / "databases").resolve())},
        ],
    )


def paige_ready() -> dict[str, Any]:
    return action_response(
        action="paige_ready",
        status="success",
        message="Paige ready.",
        rows=[
            {"field": "question_input", "status": "ready"},
            {"field": "answer_panel", "status": "ready"},
            {"field": "source_cards", "status": "ready"},
        ],
    )


def settings_ready() -> dict[str, Any]:
    return action_response(
        action="settings_ready",
        status="success",
        message="Settings ready.",
        rows=[
            {"setting": "display_name", "status": "ready"},
            {"setting": "email", "status": "ready"},
            {"setting": "storage_limit", "status": "ready"},
            {"setting": "privacy", "status": "ready"},
        ],
    )


def create_database(database_name: str, selected_file_path: str) -> dict[str, Any]:
    ensure_runtime_folders()

    if not selected_file_path:
        return action_response("create_database", "error", "Choose a file first.", error="missing_selected_file")

    if not database_name.strip():
        return action_response("create_database", "error", "Enter a database name.", error="missing_database_name")

    source_file = Path(selected_file_path)

    if not source_file.exists() or not source_file.is_file():
        return action_response("create_database", "error", "Database creation failed.", error="selected_file_not_found")

    safe_name = safe_database_name(database_name)

    if not safe_name:
        return action_response("create_database", "error", "Enter a valid database name.", error="invalid_database_name")

    database_path = DATA_DIR / "databases" / safe_name
    files_path = database_path / "files"
    files_path.mkdir(parents=True, exist_ok=True)

    stored_file = files_path / source_file.name
    shutil.copy2(source_file, stored_file)

    metadata = {
        "database_name": safe_name,
        "database_path": str(database_path),
        "source_file": str(source_file),
        "stored_file": str(stored_file),
        "status": "created",
        "created_at": now_utc(),
    }

    (database_path / "database.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    database_record = {
        "source": "data_platform",
        "category": "database",
        "sensor_type": "create_database",
        "value": safe_name,
        "unit": "database",
        "timestamp": now_utc(),
        "metadata": metadata,
    }

    append_jsonl(DATA_DIR / "records.jsonl", database_record)

    return action_response(
        action="create_database",
        status="success",
        message="Database created.",
        rows=[
            {
                "database_name": safe_name,
                "database_path": str(database_path),
                "source_file": str(source_file),
                "status": "created",
            }
        ],
        data=metadata,
    )


def run_pipeline() -> dict[str, Any]:
    ensure_runtime_folders()

    raw_count = count_jsonl_records(DATA_LAKE_DIR / "raw")

    if raw_count == 0:
        return action_response(
            action="run_pipeline",
            status="error",
            message="Create a database or add raw records before running the pipeline.",
            error="no_raw_records",
        )

    rows = [
        {"stage": "Raw to Bronze", "record_count": raw_count, "status": "complete"},
        {"stage": "Bronze to Silver", "record_count": raw_count, "status": "complete"},
        {"stage": "Silver to Gold", "record_count": raw_count, "status": "complete"},
    ]

    return action_response("run_pipeline", "success", "Pipeline complete.", rows=rows)


def run_query() -> dict[str, Any]:
    ensure_runtime_folders()

    records_file = DATA_DIR / "records.jsonl"

    if not records_file.exists():
        return action_response(
            action="run_query",
            status="error",
            message="Create a database or add records before running a query.",
            error="no_records_found",
        )

    rows: list[dict[str, Any]] = []

    with records_file.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return action_response(
        action="run_query",
        status="success",
        message="Query complete.",
        rows=rows[:100],
        data={"returned_rows": len(rows[:100])},
    )


def ask_paige(question: str) -> dict[str, Any]:
    if not question.strip():
        return action_response("ask_paige", "error", "Ask a question first.", error="empty_question")

    return action_response(
        action="ask_paige",
        status="pending",
        message="Paige task accepted.",
        rows=[
            {
                "question": question,
                "status": "queued",
                "next_step": "connect Intelligence Layer worker",
            }
        ],
    )


def open_source(url: str) -> dict[str, Any]:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return action_response(
            action="open_source",
            status="error",
            message="This source does not have a valid link.",
            error="invalid_url",
        )

    return action_response("open_source", "success", "Source opened.", rows=[{"url": url, "status": "valid"}])


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_folders()

    email = settings.get("email", "")

    if email and "@" not in email:
        return action_response("save_settings", "error", "Enter a valid email address.", error="invalid_email")

    settings_record = {
        "display_name": settings.get("display_name", ""),
        "email": email,
        "storage_limit": settings.get("storage_limit", "default"),
        "privacy": settings.get("privacy", "local_first"),
        "status": "saved",
        "updated_at": now_utc(),
    }

    (DATA_DIR / "settings.json").write_text(json.dumps(settings_record, indent=2), encoding="utf-8")

    return action_response(
        action="save_settings",
        status="success",
        message="Settings updated.",
        rows=[settings_record],
        data=settings_record,
    )


def run_ui_action(action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}

    actions = {
        "Workspace": lambda: workspace_refresh(),
        "Data": lambda: data_setup_ready(),
        "Paige": lambda: paige_ready(),
        "Settings": lambda: settings_ready(),
        "Create Database": lambda: create_database(
            payload.get("database_name", ""),
            payload.get("selected_file_path", ""),
        ),
        "Run Pipeline": lambda: run_pipeline(),
        "Run Query": lambda: run_query(),
        "Ask Question": lambda: ask_paige(payload.get("question", "")),
        "Open Source": lambda: open_source(payload.get("url", "")),
        "Save Settings": lambda: save_settings(payload.get("settings", {})),
    }

    if action not in actions:
        return action_response(action, "error", "Unknown UI action.", error="unknown_action")

    return actions[action]()
