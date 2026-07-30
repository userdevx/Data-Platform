from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from engine.intelligence.vision.models import (
    MediaFrame,
)


@runtime_checkable
class FrameSource(Protocol):
    def frames(self) -> Iterable[MediaFrame]:
        """Yield frames in capture order."""
        ...
