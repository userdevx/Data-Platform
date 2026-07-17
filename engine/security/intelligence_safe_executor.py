from __future__ import annotations

from typing import Any

from engine.security.intelligence_action_request import IntelligenceActionRequest
from engine.security.intelligence_action_validator import validate_intelligence_action_request
from engine.security.intelligence_audit import (
    log_intelligence_allowed_action,
    log_intelligence_blocked_action,
)
from engine.system.system_readers import read_cpu, read_disk, read_memory, read_uptime
from engine.tools.file_tools import read_approved_file
from engine.tools.internet_search_tool import read_web_page, search_web


def execute_intelligence_action(action_request: IntelligenceActionRequest) -> dict[str, Any]:
    try:
        validate_intelligence_action_request(action_request)

        result = run_safe_intelligence_tool(
            tool_name=action_request.tool_name,
            params=action_request.params,
        )

        log_intelligence_allowed_action(
            request_id=action_request.request_id,
            requested_by=action_request.requested_by,
            tool_name=action_request.tool_name,
            result=result,
        )

        return {
            "source": "intelligence",
            "category": "execution",
            "sensor_type": "intelligence_execution_result",
            "value": "success",
            "unit": "status",
            "status": "success",
            "request_id": action_request.request_id,
            "tool_name": action_request.tool_name,
            "result": result,
            "created_at": action_request.created_at,
        }

    except Exception as error:
        reason = str(error)

        log_intelligence_blocked_action(
            request_id=action_request.request_id,
            requested_by=action_request.requested_by,
            tool_name=action_request.tool_name,
            reason=reason,
        )

        return {
            "source": "intelligence",
            "category": "security",
            "sensor_type": "intelligence_blocked_execution_request",
            "value": action_request.tool_name,
            "unit": "tool_name",
            "status": "blocked",
            "request_id": action_request.request_id,
            "tool_name": action_request.tool_name,
            "reason": reason,
            "created_at": action_request.created_at,
        }


def run_safe_intelligence_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "system.read_cpu":
        return read_cpu()

    if tool_name == "system.read_memory":
        return read_memory()

    if tool_name == "system.read_disk":
        return read_disk()

    if tool_name == "system.read_uptime":
        return read_uptime()

    if tool_name == "files.read_approved":
        return read_approved_file(params["path"])

    if tool_name == "internet.search_web":
        return search_web(
            query=params["query"],
            limit=params.get("limit", 5),
        )

    if tool_name == "internet.read_page":
        return read_web_page(
            url=params["url"],
            title=params.get("title", ""),
        )

    raise ValueError(f"No safe Intelligence Runtime executor exists for tool: {tool_name}")
