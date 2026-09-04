"""Read resource information from the current worker cgroup."""

from __future__ import annotations

from pathlib import Path


CGROUP_ROOT = Path("/sys/fs/cgroup")
SELF_CGROUP = Path("/proc/self/cgroup")


def own_cgroup_path() -> Path | None:
    """Resolve the cgroup v2 directory for the calling process."""

    if not SELF_CGROUP.is_file():
        return None

    try:
        content = SELF_CGROUP.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in content.splitlines():
        parts = line.split(":", 2)

        if len(parts) != 3 or parts[0] != "0":
            continue

        relative = parts[2].strip().lstrip("/")
        candidate = CGROUP_ROOT / relative

        return candidate if candidate.is_dir() else None

    return None


def _read_int(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not raw or raw == "max":
        return None

    try:
        return int(raw)
    except ValueError:
        return None


def read_memory_peak_bytes() -> int | None:
    """Return the cgroup high-water mark, or None when unavailable."""

    cgroup = own_cgroup_path()

    if cgroup is None:
        return None

    peak = _read_int(cgroup / "memory.peak")

    if peak is not None:
        return peak

    return _read_int(cgroup / "memory.max_usage_in_bytes")


def read_memory_limit_bytes() -> int | None:
    cgroup = own_cgroup_path()

    if cgroup is None:
        return None

    return _read_int(cgroup / "memory.max")
