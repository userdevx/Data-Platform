import os
import cv2
import socket
from datetime import datetime, timezone


CAMERA_OUTPUT_DIR = "output/camera"


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def get_host():
    return socket.gethostname()


def ensure_camera_output_dir():
    os.makedirs(CAMERA_OUTPUT_DIR, exist_ok=True)


def capture_and_save_image(camera_index=0):
    ensure_camera_output_dir()

    camera = cv2.VideoCapture(camera_index)

    if not camera.isOpened():
        camera.release()
        return None

    success, frame = camera.read()
    camera.release()

    if not success:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = f"{CAMERA_OUTPUT_DIR}/camera_{timestamp}.jpg"

    saved = cv2.imwrite(file_path, frame)

    if not saved:
        return None

    height, width, channels = frame.shape

    return {
        "file_path": file_path,
        "width": width,
        "height": height,
        "channels": channels
    }


def get_camera_record(camera_index=0):
    image_data = capture_and_save_image(camera_index)

    if image_data is None:
        return None

    now = current_timestamp()

    return {
        "source": "system",
        "host": get_host(),
        "category": "media",
        "data_type": "camera_image",
        "value": image_data["file_path"],
        "unit": "file_path",
        "metadata": {
            "width": image_data["width"],
            "height": image_data["height"],
            "channels": image_data["channels"]
        },
        "created_at": now,
        "updated_at": now
    }
