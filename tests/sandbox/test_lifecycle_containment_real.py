from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from engine.sandbox.lifecycle.containment import (
    new_scope,
    require_host_containment,
    scope_pids,
    terminate_scope,
)
from engine.sandbox.process_identity import (
    process_start_time,
)


_WAIT_SECONDS = 10.0


def _process_state(
    pid: int,
) -> str | None:
    try:
        text = Path(
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
        fields = text.rsplit(
            ")",
            1,
        )[1].split()
    except IndexError:
        return None

    if not fields:
        return None

    return fields[0]


def _process_executing(
    pid: int,
    start_time: str,
) -> bool:
    current = process_start_time(
        pid
    )

    if current != start_time:
        return False

    # Zombie means the process has already
    # terminated and cannot execute code.
    return _process_state(pid) != "Z"


def _wait_for(
    predicate,
    timeout: float = _WAIT_SECONDS,
) -> bool:
    deadline = (
        time.monotonic()
        + timeout
    )

    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.05)

    return predicate()


def test_systemd_scope_kills_setsid_descendant(
    tmp_path: Path,
) -> None:
    require_host_containment()

    scope = new_scope()

    pid_file = (
        tmp_path
        / "escaped.pid"
    )

    # Launcher remains in the transient scope.
    # It spawns a descendant into an entirely
    # new session/process group.
    launcher_code = r'''
import subprocess
import sys

child_code = r"""
import os
import sys
import time
from pathlib import Path

pid_file = Path(sys.argv[1])

text = Path(
    f"/proc/{os.getpid()}/stat"
).read_text(
    encoding="utf-8",
)

start = (
    text.rsplit(")", 1)[1]
    .split()[19]
)

pid_file.write_text(
    f"{os.getpid()} {start}\n",
    encoding="utf-8",
)

while True:
    time.sleep(60)
"""

child = subprocess.Popen(
    [
        sys.executable,
        "-c",
        child_code,
        sys.argv[1],
    ],
    start_new_session=True,
)

child.wait()
'''

    command = [
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        f"--unit={scope.unit}",
        sys.executable,
        "-c",
        launcher_code,
        str(pid_file),
    ]

    controller = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    escaped_pid: int | None = None
    start_time: str | None = None

    try:
        assert _wait_for(
            pid_file.exists,
        ), (
            "setsid descendant did not "
            "publish its PID"
        )

        (
            pid_text,
            start_time,
        ) = (
            pid_file.read_text(
                encoding="utf-8",
            )
            .strip()
            .split()
        )

        escaped_pid = int(
            pid_text
        )

        assert _process_executing(
            escaped_pid,
            start_time,
        )

        # Prove it really escaped into its own
        # session/process group.
        assert (
            os.getsid(
                escaped_pid
            )
            == escaped_pid
        )

        assert (
            os.getpgid(
                escaped_pid
            )
            == escaped_pid
        )

        # Despite setsid(), it must remain in
        # the transient execution cgroup.
        assert (
            escaped_pid
            in scope_pids(
                scope
            )
        )

        terminate_scope(
            scope,
        )

        # The security property is that the
        # escaped process can no longer execute.
        assert _wait_for(
            lambda: not _process_executing(
                escaped_pid,
                start_time,
            )
        )

        # The execution cgroup must contain no
        # remaining runnable processes.
        assert (
            scope_pids(
                scope
            )
            == set()
        )

        # Allow systemd-run / the process parent
        # to reap a short-lived zombie.
        try:
            controller.wait(
                timeout=5
            )
        except subprocess.TimeoutExpired:
            pass

        print(
            "REAL_SETSID_CGROUP_"
            "CONTAINMENT_OK"
        )

    finally:
        try:
            terminate_scope(
                scope,
                timeout_seconds=5,
            )
        except Exception:
            pass

        if controller.poll() is None:
            controller.send_signal(
                signal.SIGKILL
            )

        try:
            controller.wait(
                timeout=5
            )
        except subprocess.TimeoutExpired:
            controller.kill()

            controller.wait(
                timeout=5
            )

        # Final safety assertion: an escaped
        # descendant must never remain runnable.
        if (
            escaped_pid is not None
            and start_time is not None
        ):
            assert not _process_executing(
                escaped_pid,
                start_time,
            )
