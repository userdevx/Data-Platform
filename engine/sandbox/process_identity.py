from __future__ import annotations

from pathlib import Path


def process_start_time(
    pid: int,
) -> str | None:
    """Return Linux process start time in kernel clock ticks.

    A PID alone is not a durable process identity because PIDs can be reused.
    The pair ``(pid, start_time)`` identifies one process instance.

    ``None`` means the process identity cannot currently be established.
    """

    if (
        isinstance(pid, bool)
        or not isinstance(pid, int)
        or pid <= 0
    ):
        raise ValueError("pid must be a positive integer")

    try:
        stat_line = Path(
            f"/proc/{pid}/stat"
        ).read_text(
            encoding="utf-8",
        )
    except (
        FileNotFoundError,
        ProcessLookupError,
        PermissionError,
    ):
        return None

    try:
        fields = stat_line.rsplit(
            ")",
            1,
        )[1].split()
    except IndexError:
        return None

    if len(fields) <= 19:
        return None

    return fields[19]


def process_identity_status(
    pid: int,
    expected_start_time: str | int | None,
) -> bool | None:
    """Return live/dead/unknown for a recorded process identity.

    True:
        PID exists and its kernel start time matches the recorded identity.

    False:
        A complete recorded identity exists but the PID is gone or has been
        reused by another process.

    None:
        The recorded identity is incomplete. Callers must fail closed and
        must not treat an unknown owner as abandoned.
    """

    if expected_start_time is None:
        return None

    expected = str(
        expected_start_time
    ).strip()

    if not expected:
        return None

    current = process_start_time(pid)

    if current is None:
        return False

    return current == expected
