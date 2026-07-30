from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from engine.intelligence.vision.models import (
    MediaFrame,
)


@dataclass(frozen=True)
class SamplingDecision:
    analyze: bool
    reason: str


class FrameSampler:
    def __init__(
        self,
        *,
        minimum_interval_ms: int,
        maximum_pending_frames: int,
    ) -> None:
        if minimum_interval_ms < 1:
            raise ValueError(
                "minimum_interval_ms must be positive."
            )

        if maximum_pending_frames < 1:
            raise ValueError(
                "maximum_pending_frames must be positive."
            )

        self.minimum_interval_ms = minimum_interval_ms
        self.maximum_pending_frames = maximum_pending_frames
        self._last_analyzed_at: datetime | None = None
        self._pending_frames = 0

    def begin_pending(self) -> None:
        self._pending_frames += 1

    def end_pending(self) -> None:
        self._pending_frames = max(
            0,
            self._pending_frames - 1,
        )

    def should_analyze(
        self,
        frame: MediaFrame,
    ) -> SamplingDecision:
        if self._pending_frames >= self.maximum_pending_frames:
            return SamplingDecision(
                analyze=False,
                reason="The visual-analysis queue is full.",
            )

        captured_at = datetime.fromisoformat(
            frame.captured_at.replace(
                "Z",
                "+00:00",
            )
        )

        if self._last_analyzed_at is None:
            self._last_analyzed_at = captured_at

            return SamplingDecision(
                analyze=True,
                reason="This is the first sampled frame.",
            )

        elapsed_ms = (
            captured_at - self._last_analyzed_at
        ).total_seconds() * 1000

        if elapsed_ms < self.minimum_interval_ms:
            return SamplingDecision(
                analyze=False,
                reason=(
                    "The configured minimum sampling "
                    "interval has not elapsed."
                ),
            )

        self._last_analyzed_at = captured_at

        return SamplingDecision(
            analyze=True,
            reason="The frame passed the sampling policy.",
        )
