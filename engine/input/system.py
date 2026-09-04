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


def build_record(data_type, value, unit="C"):
    now = current_timestamp()

    return {
        "source": "system",
        "host": get_host(),
        "category": "device_status",
        "data_type": data_type,
        "value": value,
        "unit": unit,
        "created_at": now,
        "updated_at": now
    }


def get_all_temperatures():
    output = run_sensors()
    records = []
    in_acpitz_section = False
    in_nvme_section = False

    for line in output.splitlines():
        stripped = line.strip()

        if not stripped:
            in_acpitz_section = False
            in_nvme_section = False
            continue

        if stripped.startswith("acpitz-acpi-"):
            in_acpitz_section = True
            in_nvme_section = False
            continue

        if stripped.startswith("nvme-pci-"):
            in_nvme_section = True
            in_acpitz_section = False
            continue

        if "Package id 0:" in stripped:
            value = extract_temperature(stripped)
            if value is not None:
                records.append(build_record("cpu_temperature", value))
            continue

        if in_acpitz_section and stripped.startswith("temp1:"):
            value = extract_temperature(stripped)
            if value is not None:
                records.append(build_record("acpi_temperature", value))
            continue

        if in_nvme_section and stripped.startswith("Composite:"):
            value = extract_temperature(stripped)
            if value is not None:
                records.append(build_record("nvme_temperature", value))
            continue

    return records
