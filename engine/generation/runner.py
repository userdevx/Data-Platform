"""Bounded execution of a generation worker."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .budget import ExecutionBudget


@dataclass(frozen=True)
class CompletedRun:
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    memory_peak_bytes: int | None
    payload: dict[str, Any] | None

    @property
    def killed_by_signal(self) -> int | None:
        if self.returncode < 0:
            return -self.returncode

        if 128 < self.returncode < 192:
            return self.returncode - 128

        return None


def _parse_worker_payload(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        candidate = line.strip()

        if not candidate.startswith("{"):
            continue

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            return parsed

    return None


def build_scope_command(
    command: Sequence[str],
    *,
    budget: ExecutionBudget,
    unit_name: str,
) -> list[str]:
    scoped = [
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        f"--unit={unit_name}",
        "-p",
        f"MemoryMax={budget.memory_max_bytes}",
        "-p",
        f"MemorySwapMax={budget.swap_max_bytes}",
        "-p",
        f"CPUQuota={budget.cpu_quota_percent}%",
        "--",
    ]

    scoped.extend(command)

    return scoped


def worker_environment(
    *,
    project_root: Path,
    budget: ExecutionBudget,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(os.environ)
    threads = str(budget.threads)

    environment.update(
        {
            "PYTHONPATH": str(project_root),
            "PYTHONUNBUFFERED": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": threads,
            "OPENBLAS_NUM_THREADS": threads,
            "MKL_NUM_THREADS": threads,
            "NUMEXPR_NUM_THREADS": threads,
        }
    )

    if extra:
        environment.update(extra)

    return environment


def run_bounded(
    command: Sequence[str],
    *,
    budget: ExecutionBudget,
    project_root: Path,
    timeout_seconds: int,
    unit_name: str,
    extra_environment: dict[str, str] | None = None,
) -> CompletedRun:
    if budget.enforced:
        argv = build_scope_command(
            command,
            budget=budget,
            unit_name=unit_name,
        )
    else:
        argv = list(command)

    environment = worker_environment(
        project_root=project_root,
        budget=budget,
        extra=extra_environment,
    )

    nice_level = budget.nice

    def _apply_priority() -> None:
        try:
            os.nice(nice_level)
        except OSError:
            pass

    started = time.monotonic()
    timed_out = False

    try:
        completed = subprocess.run(
            argv,
            cwd=project_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            start_new_session=True,
            preexec_fn=_apply_priority,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr

    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = -9
        stdout = error.stdout or ""
        stderr = error.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")

    duration_ms = int((time.monotonic() - started) * 1000)
    payload = _parse_worker_payload(stdout)

    memory_peak: int | None = None

    if isinstance(payload, dict):
        raw_peak = payload.get("memory_peak_bytes")

        if isinstance(raw_peak, int):
            memory_peak = raw_peak

    return CompletedRun(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        memory_peak_bytes=memory_peak,
        payload=payload,
    )
