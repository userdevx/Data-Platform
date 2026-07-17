import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PAIGE_AUDIT_LOG_PATH = Path("data/security/intelligence_execution_events.jsonl")


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_intelligence_audit_event(event: dict[str, Any]) -> None:
    PAIGE_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with PAIGE_AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def log_intelligence_allowed_action(
    request_id: str,
    requested_by: str,
    tool_name: str,
    result: dict[str, Any],
) -> None:
    append_intelligence_audit_event(
        {
            "source": "intelligence",
            "category": "security",
            "sensor_type": "intelligence_allowed_execution_request",
            "value": tool_name,
            "unit": "tool_name",
            "status": "allowed",
            "request_id": request_id,
            "requested_by": requested_by,
            "result_source": result.get("source"),
            "result_category": result.get("category"),
            "result_sensor_type": result.get("sensor_type"),
            "created_at": current_timestamp(),
        }
    )


def log_intelligence_blocked_action(
    request_id: str,
    requested_by: str,
    tool_name: str,
    reason: str,
) -> None:
    append_intelligence_audit_event(
        {
            "source": "intelligence",
            "category": "security",
            "sensor_type": "intelligence_blocked_execution_request",
            "value": tool_name,
            "unit": "tool_name",
            "status": "blocked",
            "request_id": request_id,
            "requested_by": requested_by,
            "reason": reason,
            "created_at": current_timestamp(),
        }
    )
