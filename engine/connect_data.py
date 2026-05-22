import os
from datetime import datetime, timezone


VALID_SOURCE_TYPES = {
    "system",
    "device",
    "file",
    "log",
    "camera",
    "api",
    "cloud_service",
    "stream",
}


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def connect_data(source_type, config=None):
    config = config or {}

    result = {
        "connected": False,
        "source_type": source_type,
        "checked_at": current_timestamp(),
        "details": {},
        "errors": [],
    }

    if source_type not in VALID_SOURCE_TYPES:
        result["errors"].append(f"unsupported source type: {source_type}")
        return result

    if source_type == "system":
        result["connected"] = True
        result["details"]["status"] = "system source available"
        return result

    if source_type == "device":
        port = config.get("port")

        if not port:
            result["errors"].append("missing device port")
            return result

        if not os.path.exists(port):
            result["errors"].append(f"device port not found: {port}")
            return result

        result["connected"] = True
        result["details"]["port"] = port
        result["details"]["status"] = "device source available"
        return result

    if source_type in {"file", "log"}:
        path = config.get("path")

        if not path:
            result["errors"].append("missing file path")
            return result

        if not os.path.exists(path):
            result["errors"].append(f"file not found: {path}")
            return result

        result["connected"] = True
        result["details"]["path"] = path
        result["details"]["status"] = f"{source_type} source available"
        return result

    if source_type == "camera":
        device_index = config.get("device_index", 0)

        result["connected"] = True
        result["details"]["device_index"] = device_index
        result["details"]["status"] = "camera source configured"
        return result

    if source_type in {"api", "cloud_service", "stream"}:
        endpoint = config.get("endpoint")

        if not endpoint:
            result["errors"].append("missing endpoint")
            return result

        result["connected"] = True
        result["details"]["endpoint"] = endpoint
        result["details"]["status"] = f"{source_type} source configured"
        return result

    return result
