from pathlib import Path

from engine.security.intelligence_execution_manifest import INTELLIGENCE_EXECUTION_MANIFEST


class FileToolError(Exception):
    pass


def read_approved_file(path: str) -> dict:
    file_path = Path(path)

    if file_path.is_absolute():
        raise FileToolError("Absolute paths are blocked.")

    if ".." in file_path.parts:
        raise FileToolError("Path traversal is blocked.")

    if not file_path.exists():
        raise FileToolError(f"File does not exist: {path}")

    if not file_path.is_file():
        raise FileToolError(f"Path is not a file: {path}")

    rule = INTELLIGENCE_EXECUTION_MANIFEST["files.read_approved"]
    max_file_size_mb = rule.get("max_file_size_mb", 25)
    max_file_size_bytes = max_file_size_mb * 1024 * 1024

    file_size = file_path.stat().st_size

    if file_size > max_file_size_bytes:
        raise FileToolError(f"File exceeds max size: {path}")

    content = file_path.read_text(encoding="utf-8", errors="replace")

    return {
        "source": "filesystem",
        "category": "approved_file",
        "sensor_type": "file_text",
        "value": content,
        "unit": "text",
        "path": str(file_path),
        "size_bytes": file_size,
    }
