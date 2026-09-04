import json
import serial
from datetime import datetime, timezone
from pathlib import Path


SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600
OUTPUT_FILE = Path("data/sensor_records.jsonl")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_record(record):
    """
    Adds engine metadata to the Arduino JSON record.
    Arduino provides:
    source, category, data_type, value, unit
    """

    return {
        "source": record.get("source", "arduino_uno_r4_wifi"),
        "category": record.get("category", "motion"),
        "data_type": record.get("data_type", "unknown"),
        "value": record.get("value"),
        "unit": record.get("unit", "unknown"),
        "timestamp": utc_now(),
        "ingested_by": "local_python_serial_reader",
    }


def store_record(record):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


def main():
    print(f"Connecting to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud...")

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as arduino:
        print("Connected. Listening for JSON records...")

        while True:
            raw_line = arduino.readline().decode("utf-8", errors="ignore").strip()

            if not raw_line:
                continue

            if not raw_line.startswith("{"):
                print(f"Ignored non-JSON line: {raw_line}")
                continue

            try:
                arduino_record = json.loads(raw_line)
                normalized_record = normalize_record(arduino_record)
                store_record(normalized_record)

                print("Stored:", normalized_record)

            except json.JSONDecodeError:
                print(f"Bad JSON ignored: {raw_line}")


if __name__ == "__main__":
    main()
