from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _immutable_mapping(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    return MappingProxyType(
        dict(value)
    )


@dataclass(frozen=True)
class VisualModelRequest:
    request_id: str
    question: str
    image_data: bytes
    media_type: str
    response_schema: Mapping[str, Any]
    source_reference: str | None = None
    metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "request_id",
            self.request_id.strip(),
        )
        object.__setattr__(
            self,
            "question",
            " ".join(
                self.question.split()
            ).strip(),
        )
        object.__setattr__(
            self,
            "media_type",
            self.media_type.strip().lower(),
        )

        if self.source_reference is not None:
            source_reference = (
                self.source_reference.strip()
            )

            object.__setattr__(
                self,
                "source_reference",
                source_reference or None,
            )

        object.__setattr__(
            self,
            "image_data",
            bytes(self.image_data),
        )
        object.__setattr__(
            self,
            "response_schema",
            _immutable_mapping(
                self.response_schema
            ),
        )
        object.__setattr__(
            self,
            "metadata",
            _immutable_mapping(
                self.metadata
            ),
        )

    @property
    def image_size_bytes(self) -> int:
        return len(self.image_data)

    def to_record(
        self,
        *,
        include_image_data: bool = False,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "request_id": self.request_id,
            "question": self.question,
            "media_type": self.media_type,
            "image_size_bytes": (
                self.image_size_bytes
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
