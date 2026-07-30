from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from engine.intelligence.vision.models import (
    MediaFrame,
)


class OpenCVCameraSource:
    def __init__(
        self,
        *,
        device_index: int = 0,
        maximum_frames: int | None = None,
    ) -> None:
        if device_index < 0:
            raise ValueError(
                "device_index cannot be negative."
            )

        if (
            maximum_frames is not None
            and maximum_frames < 1
        ):
            raise ValueError(
                "maximum_frames must be positive."
            )

        self.device_index = device_index
        self.maximum_frames = maximum_frames
        self.source_id = uuid4().hex
        self.sequence_id = uuid4().hex

    def frames(self) -> Iterable[MediaFrame]:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError(
                "OpenCV is required for camera capture."
            ) from error

        capture = cv2.VideoCapture(
            self.device_index
        )

        if not capture.isOpened():
            capture.release()

            raise RuntimeError(
                "The configured camera could not be opened."
            )

        with TemporaryDirectory(
            prefix="visual-frames-"
        ) as directory:
            temporary_root = Path(directory)
            frame_index = 0

            try:
                while True:
                    if (
                        self.maximum_frames is not None
                        and frame_index
                        >= self.maximum_frames
                    ):
                        break

                    success, image = capture.read()

                    if not success:
                        break

                    frame_path = (
                        temporary_root
                        / f"{frame_index:08d}.jpg"
                    )

                    written = cv2.imwrite(
                        str(frame_path),
                        image,
                    )

                    if not written:
                        raise RuntimeError(
                            "A captured frame could not be written."
                        )

                    height, width = image.shape[:2]

                    yield MediaFrame(
                        frame_id=uuid4().hex,
                        source_id=self.source_id,
                        sequence_id=self.sequence_id,
                        frame_index=frame_index,
                        captured_at=(
                            datetime.now(UTC).isoformat()
                        ),
                        media_location=str(frame_path),
                        media_type="image/jpeg",
                        width=int(width),
                        height=int(height),
                    )

                    frame_index += 1
            finally:
                capture.release()
