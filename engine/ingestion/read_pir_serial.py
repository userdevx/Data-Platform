import json
import time
import uuid
from datetime import datetime, timezone

import serial

from engine.storage.json_backend import LocalJsonStorageBackend


# -----------------------------
# Arduino serial settings
# -----------------------------
PORT = "/dev/ttyACM0"
BAUD_RATE = 9600


# -----------------------------
# Local-first storage file
# This stores records on your laptop.
# No cloud. No internet. No external server.
# -----------------------------
DATA_FILE = "data/records.json"


# -----------------------------
# Create local storage engine
# -----------------------------
storage = LocalJsonStorageBackend(DATA_FILE)


def normalize_record(raw_record):
    """
    Convert the raw Arduino JSON into the data engine record format.
    """

    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "id": str(uuid.uuid4()),
        "source": raw_record.get("source", "arduino_uno_r4_wifi"),
        "category": raw_record.get("category", "motion"),
        "data_type": raw_record.get("data_type", "hc_sr501_pir"),
        "value": raw_record.get("value"),
        "unit": raw_record.get("unit", "boolean"),
        "timestamp": timestamp,
        "created_at": timestamp,
        "ingested_by": "local_python_serial_reader",
    }


def handle_alert(record):
    """
    Local terminal alert.
    This does not use internet yet.
    """

    if record["category"] == "motion" and record["value"] is True:
        print("ALERT: Motion detected")


def main():
    print(f"Opening Arduino serial port: {PORT}")

    with serial.Serial(PORT, BAUD_RATE, timeout=1) as arduino:
        time.sleep(2)

        print("Connected to Arduino.")
        print("Reading motion records...")
        print("Press CTRL + C to stop.")

        while True:
            line = arduino.readline().decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            print("RAW:", line)

            try:
                raw_record = json.loads(line)
            except json.JSONDecodeError:
                print("Skipped non-JSON line")
                continue

            record = normalize_record(raw_record)

            storage.insert_record(record)

            print("SAVED:", record)

            handle_alert(record)


if __name__ == "__main__":
    main()
