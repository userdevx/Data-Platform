from datetime import datetime, timezone

import psutil


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_cpu() -> dict:
    return {
        "source": "system",
        "category": "device_status",
        "sensor_type": "cpu_percent",
        "value": psutil.cpu_percent(interval=1),
        "unit": "%",
        "created_at": current_timestamp(),
    }


def read_memory() -> dict:
    memory = psutil.virtual_memory()

    return {
        "source": "system",
        "category": "device_status",
        "sensor_type": "memory_percent",
        "value": memory.percent,
        "unit": "%",
        "created_at": current_timestamp(),
    }


def read_disk() -> dict:
    disk = psutil.disk_usage("/")

    return {
        "source": "system",
        "category": "device_status",
        "sensor_type": "disk_percent",
        "value": disk.percent,
        "unit": "%",
        "created_at": current_timestamp(),
    }


def read_uptime() -> dict:
    boot_time = psutil.boot_time()
    now = datetime.now(timezone.utc).timestamp()
    uptime_seconds = int(now - boot_time)

    return {
        "source": "system",
        "category": "device_status",
        "sensor_type": "uptime_seconds",
        "value": uptime_seconds,
        "unit": "seconds",
        "created_at": current_timestamp(),
    }
