from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass(
    frozen=True,
    kw_only=True,
)
class RealTimeObservation:
    source: str
    category: str
    data_type: str
    sensor_type: str
    value: Any
    unit: str

    observation_id: str = field(
        default_factory=lambda: str(
            uuid4()
        )
    )

    observed_at: str = field(
        default_factory=utc_now
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(
    frozen=True,
    kw_only=True,
)
class SystemSnapshot:
    cpu: dict[str, Any]
    memory: dict[str, Any]
    disk: dict[str, Any]
    uptime: dict[str, Any]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "cpu": dict(
                self.cpu
            ),
            "memory": dict(
                self.memory
            ),
            "disk": dict(
                self.disk
            ),
            "uptime": dict(
                self.uptime
            ),
        }
