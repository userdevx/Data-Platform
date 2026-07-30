from __future__ import annotations

from typing import Protocol, runtime_checkable

from engine.intelligence.vision.models import (
    MediaFrame,
    VisualAnalysisRequest,
    VisualObservation,
)


@runtime_checkable
class VisualAnalyzer(Protocol):
    def analyze(
        self,
        *,
        request: VisualAnalysisRequest,
        frame: MediaFrame,
    ) -> VisualObservation:
        """Analyze one frame according to the runtime query."""
        ...
