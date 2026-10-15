from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .cancellation import CancellationToken


TIMEOUT_EXIT_CODE = 124
CANCELLED_EXIT_CODE = 130

DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024

_POLL_SECONDS = 0.02
_READ_CHUNK = 65536


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    argv: tuple[str, ...]
    pid: int
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    cancelled: bool
    duration_seconds: float
    stdout_truncated: bool
    stderr_truncated: bool


class _BoundedReader(threading.Thread):
    """Drain a pipe completely while retaining only a bounded prefix."""

    def __init__(
        self,
        stream,
        limit: int,
    ) -> None:
        super().__init__(daemon=True)

        self._stream = stream
        self._limit = limit
        self._chunks: list[bytes] = []
        self._kept = 0

        self.truncated = False

    def run(self) -> None:
        try:
            while True:
                chunk = self._stream.read1(_READ_CHUNK)

                if not chunk:
                    return

                room = self._limit - self._kept

                if room > 0:
                    kept = chunk[:room]
                    self._chunks.append(kept)
                    self._kept += len(kept)

                if len(chunk) > max(room, 0):
                    self.truncated = True

        except (OSError, ValueError):
            return

    def text(self) -> str:
        return b"".join(self._chunks).decode(
            "utf-8",
            errors="replace",
        )


def _exit_code_from_status(status: int) -> int:
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)

    return os.waitstatus_to_exitcode(status)


def _signal_group(
    pgid: int,
    sig: signal.Signals,
) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def process_group_members(
    pgid: int,
) -> list[int]:
    """Return non-zombie members of a Linux process group."""

    members: list[int] = []

    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue

        try:
            stat_text = (entry / "stat").read_text(
                encoding="utf-8",
            )
        except OSError:
            continue

        try:
            fields = stat_text.rsplit(")", 1)[1].split()
            state = fields[0]
            process_group = int(fields[2])
        except (IndexError, ValueError):
            continue

        if process_group == pgid and state != "Z":
            members.append(int(entry.name))

    return members


def terminate_process_group(
    pgid: int,
    *,
    grace_seconds: float = 5.0,
) -> None:
    if grace_seconds < 0:
        raise ValueError(
            "grace_seconds must not be negative"
        )

    _signal_group(pgid, signal.SIGTERM)

    deadline = time.monotonic() + grace_seconds

    while time.monotonic() < deadline:
        if not process_group_members(pgid):
            return

        time.sleep(_POLL_SECONDS)

    _signal_group(pgid, signal.SIGKILL)


def terminate_popen(
    process: subprocess.Popen,
    *,
    grace_seconds: float = 5.0,
) -> None:
    if process.poll() is not None:
        return

    try:
        leads_group = (
            os.getpgid(process.pid) == process.pid
        )
    except ProcessLookupError:
        return

    if leads_group:
        _signal_group(
            process.pid,
            signal.SIGTERM,
        )
    else:
        process.terminate()

    try:
        process.wait(timeout=grace_seconds)

    except subprocess.TimeoutExpired:
        if leads_group:
            _signal_group(
                process.pid,
                signal.SIGKILL,
            )
        else:
            process.kill()

        process.wait(timeout=grace_seconds)

    if leads_group:
        _signal_group(
            process.pid,
            signal.SIGKILL,
        )


def run_process(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    environment: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    stdin_data: bytes | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    cancellation: CancellationToken | None = None,
    grace_seconds: float = 5.0,
) -> ProcessOutcome:
    if not argv:
        raise ValueError("argv must not be empty")

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be greater than zero"
        )

    if max_output_bytes < 0:
        raise ValueError(
            "max_output_bytes must not be negative"
        )

    if cancellation is not None:
        cancellation.raise_if_cancelled()

    started = time.monotonic()

    process = subprocess.Popen(
        list(argv),
        stdin=(
            subprocess.PIPE
            if stdin_data is not None
            else subprocess.DEVNULL
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=(
            dict(environment)
            if environment is not None
            else None
        ),
        cwd=(
            str(cwd)
            if cwd is not None
            else None
        ),
        start_new_session=True,
        close_fds=True,
    )

    process_group = process.pid

    if process.stdout is None or process.stderr is None:
        raise RuntimeError(
            "subprocess output pipes unavailable"
        )

    stdout_reader = _BoundedReader(
        process.stdout,
        max_output_bytes,
    )

    stderr_reader = _BoundedReader(
        process.stderr,
        max_output_bytes,
    )

    stdout_reader.start()
    stderr_reader.start()

    if (
        stdin_data is not None
        and process.stdin is not None
    ):

        def feed_stdin() -> None:
            try:
                process.stdin.write(stdin_data)
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        threading.Thread(
            target=feed_stdin,
            daemon=True,
        ).start()

    deadline = started + timeout_seconds

    timed_out = False
    cancelled = False
    status: int | None = None

    try:
        while True:
            reaped_pid, raw_status, _ = os.wait4(
                process.pid,
                os.WNOHANG,
            )

            if reaped_pid == process.pid:
                status = raw_status
                break

            if (
                cancellation is not None
                and cancellation.cancelled
            ):
                cancelled = True
                break

            if time.monotonic() >= deadline:
                timed_out = True
                break

            time.sleep(_POLL_SECONDS)

        if status is None:
            terminate_process_group(
                process_group,
                grace_seconds=grace_seconds,
            )

            _, status, _ = os.wait4(
                process.pid,
                0,
            )

        if process_group_members(process_group):
            terminate_process_group(
                process_group,
                grace_seconds=grace_seconds,
            )

    finally:
        if status is None:
            _signal_group(
                process_group,
                signal.SIGKILL,
            )

            try:
                _, status, _ = os.wait4(
                    process.pid,
                    0,
                )
            except ChildProcessError:
                status = 0

        process.returncode = _exit_code_from_status(
            status
        )

    stdout_reader.join(timeout=grace_seconds)
    stderr_reader.join(timeout=grace_seconds)

    for stream in (
        process.stdout,
        process.stderr,
    ):
        try:
            stream.close()
        except OSError:
            pass

    if timed_out:
        exit_code = TIMEOUT_EXIT_CODE

    elif cancelled:
        exit_code = CANCELLED_EXIT_CODE

    else:
        exit_code = _exit_code_from_status(status)

    return ProcessOutcome(
        argv=tuple(argv),
        pid=process.pid,
        exit_code=exit_code,
        stdout=stdout_reader.text(),
        stderr=stderr_reader.text(),
        timed_out=timed_out,
        cancelled=cancelled,
        duration_seconds=(
            time.monotonic() - started
        ),
        stdout_truncated=stdout_reader.truncated,
        stderr_truncated=stderr_reader.truncated,
    )
