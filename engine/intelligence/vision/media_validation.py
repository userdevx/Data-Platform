from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaValidationResult:
    allowed: bool
    reason: str
    size_bytes: int
    media_type: str


def validate_media_file(
    *,
    media_path: Path,
    maximum_size_bytes: int,
) -> MediaValidationResult:
    if maximum_size_bytes < 1:
        raise ValueError(
            "maximum_size_bytes must be positive."
        )

    if not media_path.is_file():
        return MediaValidationResult(
            allowed=False,
            reason="The media file does not exist.",
            size_bytes=0,
            media_type="",
        )

    size_bytes = media_path.stat().st_size

    if size_bytes < 1:
        return MediaValidationResult(
            allowed=False,
            reason="The media file is empty.",
            size_bytes=size_bytes,
            media_type="",
        )

    media_type = (
        mimetypes.guess_type(media_path.name)[0]
        or ""
    )

    if not media_type.startswith("image/"):
        return MediaValidationResult(
            allowed=False,
            reason="The file is not a supported image media type.",
            size_bytes=size_bytes,
            media_type=media_type,
        )

    if size_bytes > maximum_size_bytes:
        return MediaValidationResult(
            allowed=False,
            reason="The media exceeds the configured size limit.",
            size_bytes=size_bytes,
            media_type=media_type,
        )

    return MediaValidationResult(
        allowed=True,
        reason="Media validation passed.",
        size_bytes=size_bytes,
        media_type=media_type,
    )
