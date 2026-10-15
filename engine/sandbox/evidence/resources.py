from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)
from typing import Any

from engine.sandbox.lifecycle.timeout import (
    ProcessOutcome,
)


@dataclass(frozen=True, slots=True)
class ResourceUsageEvidence:
    user_cpu_seconds: float
    system_cpu_seconds: float
    total_cpu_seconds: float
    max_rss_kb: int
    voluntary_context_switches: int
    involuntary_context_switches: int

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


def resource_usage_evidence(
    outcome: ProcessOutcome,
) -> ResourceUsageEvidence:
    if not isinstance(
        outcome,
        ProcessOutcome,
    ):
        raise TypeError(
            "outcome must be a ProcessOutcome"
        )

    return ResourceUsageEvidence(
        user_cpu_seconds=(
            outcome.user_cpu_seconds
        ),
        system_cpu_seconds=(
            outcome.system_cpu_seconds
        ),
        total_cpu_seconds=(
            outcome.user_cpu_seconds
            + outcome.system_cpu_seconds
        ),
        max_rss_kb=(
            outcome.max_rss_kb
        ),
        voluntary_context_switches=(
            outcome.voluntary_context_switches
        ),
        involuntary_context_switches=(
            outcome.involuntary_context_switches
        ),
    )
