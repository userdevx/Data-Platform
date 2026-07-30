from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from engine.intelligence.vision.models import (
    MediaFrame,
)


class StillImageSource:
    def __init__(
        self,
        *,
        media_path: Path,
        media_type: str,
        source_id: str | None = None,
        sequence_id: str | None = None,
    ) -> None:
        self.media_path = media_path
        self.media_type = media_type
        self.source_id = source_id or uuid4().hex
        self.sequence_id = sequence_id or uuid4().hex

    def frames(self) -> Iterable[MediaFrame]:
        yield MediaFrame(
            frame_id=uuid4().hex,
            source_id=self.source_id,
            sequence_id=self.sequence_id,
            frame_index=0,
            captured_at=datetime.now(UTC).isoformat(),
            media_location=str(self.media_path),
            media_type=self.media_type,
        )
