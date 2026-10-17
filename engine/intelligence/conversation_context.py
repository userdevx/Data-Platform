from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engine.backend import get_backend
from engine.data_engine.record_writer import DataEngineRecordWriter
from engine.query import QueryService


CONVERSATION_CATEGORY = "conversation"
USER_INQUIRY = "user_inquiry"
INTELLIGENCE_RESPONSE = "intelligence_response"


class ConversationContext:
    """
    Data Platform conversation state.

    Conversation is stored through the same Data Engine used by the rest
    of the platform. There is no independent chat-history database.
    """

    def __init__(self) -> None:
        backend = get_backend()
        self.query_service = QueryService(backend)
        self.writer = DataEngineRecordWriter(
            query_service=self.query_service
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def store_inquiry(
        self,
        text: str,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        text = str(text or "").strip()

        if not text:
            raise ValueError("Inquiry text is required.")

        return self.writer.write(
            source="application_interface",
            category=CONVERSATION_CATEGORY,
            data_type=USER_INQUIRY,
            value={
                "text": text,
                "request_id": request_id,
                "created_at": self._now(),
            },
            unit="record",
        )

    def store_response(
        self,
        text: str,
        *,
        request_id: str | None = None,
        capability: str | None = None,
        route: str | None = None,
    ) -> dict[str, Any]:
        text = str(text or "").strip()

        if not text:
            raise ValueError("Response text is required.")

        return self.writer.write(
            source="intelligence_runtime",
            category=CONVERSATION_CATEGORY,
            data_type=INTELLIGENCE_RESPONSE,
            value={
                "text": text,
                "request_id": request_id,
                "capability": capability,
                "route": route,
                "created_at": self._now(),
            },
            unit="record",
        )

    def recent_records(
        self,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        records = self.query_service.filter_by_field(
            "category",
            CONVERSATION_CATEGORY,
        )

        conversation_records = [
            record
            for record in records
            if record.get("data_type")
            in {
                USER_INQUIRY,
                INTELLIGENCE_RESPONSE,
            }
        ]

        def created_at(record: dict[str, Any]) -> str:
            value = record.get("value")

            if isinstance(value, dict):
                return str(value.get("created_at") or "")

            return ""

        conversation_records.sort(
            key=created_at
        )

        return conversation_records[-limit:]

    def build_context(
        self,
        limit: int = 12,
    ) -> str:
        records = self.recent_records(limit)

        if not records:
            return ""

        lines: list[str] = []

        for record in records:
            value = record.get("value")

            if not isinstance(value, dict):
                continue

            text = str(
                value.get("text") or ""
            ).strip()

            if not text:
                continue

            data_type = record.get("data_type")

            if data_type == USER_INQUIRY:
                role = "User"
            elif data_type == INTELLIGENCE_RESPONSE:
                role = "Intelligence"
            else:
                continue

            lines.append(
                f"{role}: {text}"
            )

        if not lines:
            return ""

        return "\n".join(lines)
