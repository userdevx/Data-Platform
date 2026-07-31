from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VisualModelRequest:
    request_id: str
    question: str
    image_data: bytes
    media_type: str
    response_schema: dict[str, Any]
    source_reference: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_record(
        self,
        *,
        include_image_data: bool = False,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "request_id": self.request_id,
            "question": self.question,
            "media_type": self.media_type,
            "image_size_bytes": len(
                self.image_data
            ),
            "response_schema": dict(
                self.response_schema
            ),
            "source_reference": (
                self.source_reference
            ),
            "metadata": dict(
                self.metadata
            ),
        }

        if include_image_data:
            record["image_data"] = (
                self.image_data
            )

        return record
