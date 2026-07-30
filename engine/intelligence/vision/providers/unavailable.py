from __future__ import annotations

from engine.intelligence.vision.models import (
    MediaFrame,
    VisualAnalysisRequest,
    VisualObservation,
)


class VisualAnalyzerUnavailableError(RuntimeError):
    """Raised when no visual provider is configured."""


class UnavailableVisualAnalyzer:
    def analyze(
        self,
        *,
        request: VisualAnalysisRequest,
        frame: MediaFrame,
    ) -> VisualObservation:
        del request
        del frame

        raise VisualAnalyzerUnavailableError(
            "No visual-analysis provider is configured."
        )
