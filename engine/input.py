import subprocess
import socket
from datetime import datetime, timezone


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def get_host():
    return socket.gethostname()


def run_sensors():
    result = subprocess.run(
        ["sensors"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout


def extract_temperature(line):
    if "+" not in line or "°C" not in line:
        return None

    try:
        value = line.split("+")[1].split("°C")[0].strip()
        return float(value)
    except (IndexError, ValueError):
        return None


def build_record(sensor_type, value, unit="C"):
    now = current_timestamp()

    return {
        "source": "system",
        "host": get_host(),
        "category": "device_status",
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit,
        "created_at": now,
        "updated_at": now
    }


def get_all_temperatures():
    output = run_sensors()
    records = []

    for line in output.splitlines():

        # CPU package temperature
        if "Package id 0:" in line:
            value = extract_temperature(line)
            if value is not None:
                records.append(build_record("cpu_temperature", value))

        # ACPI temperature (skip header line)
        elif "acpitz" in line.lower():
            continue

        elif "temp1:" in line:
            value = extract_temperature(line)
            if value is not None:
                records.append(build_record("acpi_temperature", value))

        # NVMe temperature
        elif "Composite:" in line:
            value = extract_temperature(line)
            if value is not None:
                records.append(build_record("nvme_temperature", value))

    return records
