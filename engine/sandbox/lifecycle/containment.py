from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


_UNIT_PATTERN = re.compile(
    r"^dataworc-sandbox-[a-f0-9]{12}\.scope$"
)


class ContainmentUnavailable(RuntimeError):
    pass


class ContainmentCleanupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SystemdScope:
    unit: str


def systemd_user_available() -> bool:
    try:
        completed = subprocess.run(
            [
                "systemctl",
                "--user",
                "is-system-running",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False

    return completed.returncode in {
        0,
        1,
    }


def cgroup_v2_available() -> bool:
    try:
        completed = subprocess.run(
            [
                "stat",
                "-fc",
                "%T",
                "/sys/fs/cgroup",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False

    return (
        completed.returncode == 0
        and completed.stdout.strip()
        == "cgroup2fs"
    )


def require_host_containment() -> None:
    if not systemd_user_available():
        raise ContainmentUnavailable(
            "systemd user manager is unavailable"
        )

    if not cgroup_v2_available():
        raise ContainmentUnavailable(
            "cgroup v2 is unavailable"
        )


def new_scope() -> SystemdScope:
    return SystemdScope(
        unit=(
            "dataworc-sandbox-"
            f"{uuid4().hex[:12]}.scope"
        )
    )


def _validate_unit(
    scope: SystemdScope,
) -> None:
    if not _UNIT_PATTERN.fullmatch(
        scope.unit
    ):
        raise ValueError(
            f"invalid sandbox scope: {scope.unit!r}"
        )


def scope_exists(
    scope: SystemdScope,
) -> bool:
    _validate_unit(scope)

    completed = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            scope.unit,
            "--property=LoadState",
            "--value",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    if completed.returncode != 0:
        return False

    return (
        completed.stdout.strip()
        not in {
            "",
            "not-found",
        }
    )


def scope_pids(
    scope: SystemdScope,
) -> set[int]:
    _validate_unit(scope)

    completed = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            scope.unit,
            "--property=ControlGroup",
            "--value",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    if completed.returncode != 0:
        return set()

    control_group = (
        completed.stdout.strip()
    )

    if not control_group:
        return set()

    relative = control_group.lstrip("/")

    procs = (
        Path("/sys/fs/cgroup")
        / relative
        / "cgroup.procs"
    )

    try:
        lines = procs.read_text(
            encoding="utf-8",
        ).splitlines()
    except OSError:
        return set()

    return {
        int(line)
        for line in lines
        if line.strip().isdigit()
    }


def terminate_scope(
    scope: SystemdScope,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    _validate_unit(scope)

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be positive"
        )

    subprocess.run(
        [
            "systemctl",
            "--user",
            "kill",
            "--kill-whom=all",
            "--signal=SIGTERM",
            scope.unit,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    deadline = (
        time.monotonic()
        + min(
            timeout_seconds,
            3.0,
        )
    )

    while time.monotonic() < deadline:
        if not scope_pids(scope):
            break

        time.sleep(0.05)

    if scope_pids(scope):
        subprocess.run(
            [
                "systemctl",
                "--user",
                "kill",
                "--kill-whom=all",
                "--signal=SIGKILL",
                scope.unit,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while time.monotonic() < deadline:
        if not scope_pids(scope):
            return

        time.sleep(0.05)

    surviving = sorted(
        scope_pids(scope)
    )

    raise ContainmentCleanupError(
        "sandbox cgroup survived termination: "
        f"{scope.unit}: {surviving}"
    )
