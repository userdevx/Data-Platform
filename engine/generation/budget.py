"""Hardware detection and execution budget derivation."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


GIB = 1024 ** 3

DEFAULT_DESKTOP_RESERVE_BYTES = 3 * GIB
MINIMUM_WORKER_MEMORY_BYTES = 2 * GIB
MAXIMUM_WORKER_MEMORY_BYTES = 16 * GIB

DEFAULT_NICE = 10
DEFAULT_MAX_CONCURRENT_JOBS = 1

PROFILE_PROTECTED = "protected"
PROFILE_UNPROTECTED = "unprotected"

CGROUP_ROOT = Path("/sys/fs/cgroup")
MEMINFO_PATH = Path("/proc/meminfo")


class InsufficientResourcesError(RuntimeError):
    """Raised when the machine cannot satisfy a minimum viable budget."""


@dataclass(frozen=True)
class HardwareSnapshot:
    total_memory_bytes: int
    available_memory_bytes: int
    total_swap_bytes: int
    free_swap_bytes: int
    cpu_count: int
    cgroup_version: int
    systemd_run_available: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionBudget:
    memory_max_bytes: int
    swap_max_bytes: int
    cpu_quota_percent: int
    nice: int
    threads: int
    max_concurrent_jobs: int
    enforced: bool
    profile: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}

    if not MEMINFO_PATH.is_file():
        return values

    for line in MEMINFO_PATH.read_text(encoding="utf-8").splitlines():
        name, _, remainder = line.partition(":")
        parts = remainder.split()

        if not parts:
            continue

        try:
            amount = int(parts[0])
        except ValueError:
            continue

        if len(parts) > 1 and parts[1].lower() == "kb":
            amount *= 1024

        values[name.strip()] = amount

    return values


def detect_cgroup_version() -> int:
    if (CGROUP_ROOT / "cgroup.controllers").is_file():
        return 2

    if (CGROUP_ROOT / "memory").is_dir():
        return 1

    return 0


def detect_systemd_run(*, probe: bool = True) -> bool:
    if shutil.which("systemd-run") is None:
        return False

    if not probe:
        return True

    try:
        completed = subprocess.run(
            [
                "systemd-run",
                "--user",
                "--scope",
                "--quiet",
                "--collect",
                "--",
                "true",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return completed.returncode == 0


def detect_hardware(*, probe_systemd: bool = True) -> HardwareSnapshot:
    meminfo = _read_meminfo()

    total_memory = meminfo.get("MemTotal", 0)
    available_memory = meminfo.get("MemAvailable", total_memory)

    return HardwareSnapshot(
        total_memory_bytes=total_memory,
        available_memory_bytes=available_memory,
        total_swap_bytes=meminfo.get("SwapTotal", 0),
        free_swap_bytes=meminfo.get("SwapFree", 0),
        cpu_count=os.cpu_count() or 1,
        cgroup_version=detect_cgroup_version(),
        systemd_run_available=detect_systemd_run(probe=probe_systemd),
    )


def derive_budget(
    snapshot: HardwareSnapshot,
    *,
    desktop_reserve_bytes: int = DEFAULT_DESKTOP_RESERVE_BYTES,
    minimum_memory_bytes: int = MINIMUM_WORKER_MEMORY_BYTES,
    maximum_memory_bytes: int = MAXIMUM_WORKER_MEMORY_BYTES,
    nice: int = DEFAULT_NICE,
    max_concurrent_jobs: int = DEFAULT_MAX_CONCURRENT_JOBS,
) -> ExecutionBudget:
    headroom = snapshot.available_memory_bytes - desktop_reserve_bytes

    if headroom < minimum_memory_bytes:
        raise InsufficientResourcesError(
            "Insufficient free memory for a generation job: "
            f"{headroom} bytes available after reserving "
            f"{desktop_reserve_bytes} bytes for the session."
        )

    memory_max = min(headroom, maximum_memory_bytes)

    reserved_cpus = max(1, snapshot.cpu_count // 4)
    threads = max(1, snapshot.cpu_count - reserved_cpus)

    enforced = (
        snapshot.systemd_run_available
        and snapshot.cgroup_version == 2
    )

    return ExecutionBudget(
        memory_max_bytes=memory_max,
        swap_max_bytes=0,
        cpu_quota_percent=threads * 100,
        nice=nice,
        threads=threads,
        max_concurrent_jobs=max_concurrent_jobs,
        enforced=enforced,
        profile=PROFILE_PROTECTED if enforced else PROFILE_UNPROTECTED,
    )


def current_budget(
    **kwargs: Any,
) -> tuple[HardwareSnapshot, ExecutionBudget]:
    snapshot = detect_hardware()
    return snapshot, derive_budget(snapshot, **kwargs)
