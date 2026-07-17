from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class IntelligenceActionRequest:
    request_id: str
    source: str
    requested_by: str
    tool_name: str
    params: dict[str, Any]
    created_at: str


def create_intelligence_action_request(
    tool_name: str,
    params: dict[str, Any] | None = None,
    source: str = "intelligence",
    requested_by: str = "intelligence",
) -> IntelligenceActionRequest:
    if params is None:
        params = {}

    return IntelligenceActionRequest(
        request_id=str(uuid4()),
        source=source,
        requested_by=requested_by,
        tool_name=tool_name,
        params=params,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
