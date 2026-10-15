from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from engine.sandbox.lifecycle.provisioning import (
    SandboxLease,
    find_abandoned_leases,
    list_leases,
    new_sandbox_id,
    release_lease,
    write_lease,
)
from engine.sandbox.process_identity import (
    process_start_time,
)


_WAIT_SECONDS = 5.0


def _wait_for(
    predicate,
    timeout: float = _WAIT_SECONDS,
) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.05)

    return predicate()


def test_killed_controller_becomes_abandoned(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    sandbox_id = new_sandbox_id(
        "test"
    )

    run_directory = (
        state
        / "runs"
        / sandbox_id
    )

    child_code = r'''
import sys
import time
from pathlib import Path

from engine.sandbox.lifecycle.provisioning import (
    acquire_lease,
)

state = Path(sys.argv[1])
sandbox_id = sys.argv[2]

run_directory = (
    state
    / "runs"
    / sandbox_id
)

run_directory.mkdir(
    parents=True,
    mode=0o700,
)

lease = acquire_lease(
    sandbox_id=sandbox_id,
    runtime="recovery-test",
    run_directory=run_directory,
    root=state,
)

print(
    f"{lease.sandbox_id}|"
    f"{lease.controller_pid}|"
    f"{lease.controller_start_ticks}",
    flush=True,
)

while True:
    time.sleep(60)
'''

    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            child_code,
            str(state),
            sandbox_id,
        ],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        assert process.stdout is not None
        assert process.stderr is not None

        identity_line = (
            process.stdout.readline().strip()
        )

        if not identity_line:
            stderr = (
                process.stderr.read()
                if process.poll() is not None
                else ""
            )

            raise AssertionError(
                "controller failed before publishing "
                f"its lease identity: {stderr}"
            )

        (
            reported_id,
            pid_text,
            start_time,
        ) = identity_line.split(
            "|",
            2,
        )

        assert reported_id == sandbox_id
        assert int(pid_text) == process.pid
        assert start_time

        assert (
            process_start_time(
                process.pid
            )
            == start_time
        )

        leases = list_leases(
            state
        )

        assert [
            lease.sandbox_id
            for lease in leases
        ] == [sandbox_id]

        assert (
            find_abandoned_leases(
                state
            )
            == []
        )

        os.kill(
            process.pid,
            signal.SIGKILL,
        )

        process.wait(
            timeout=5
        )

        assert _wait_for(
            lambda: process_start_time(
                process.pid
            )
            is None
        )

        abandoned = (
            find_abandoned_leases(
                state
            )
        )

        assert [
            lease.sandbox_id
            for lease in abandoned
        ] == [sandbox_id]

        lease = abandoned[0]

        assert (
            lease.controller_status()
            is False
        )

        assert (
            Path(
                lease.run_directory
            )
            == run_directory
        )

        # A controller crash must leave both the
        # lease and run directory discoverable.
        assert run_directory.exists()

        print(
            "REAL_KILLED_CONTROLLER_"
            "ABANDONED_LEASE_OK"
        )

    finally:
        if process.poll() is None:
            os.kill(
                process.pid,
                signal.SIGKILL,
            )

            process.wait(
                timeout=5
            )

        release_lease(
            sandbox_id,
            state,
        )


def test_unknown_owner_identity_fails_closed(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"

    sandbox_id = new_sandbox_id(
        "test"
    )

    run_directory = (
        state
        / "runs"
        / sandbox_id
    )

    run_directory.mkdir(
        parents=True,
        mode=0o700,
    )

    lease = SandboxLease(
        sandbox_id=sandbox_id,
        runtime="recovery-test",
        controller_pid=os.getpid(),
        controller_start_ticks=None,
        created_at=(
            "2026-10-14T00:00:00+00:00"
        ),
        run_directory=str(
            run_directory
        ),
        resources=(),
    )

    write_lease(
        lease,
        state,
    )

    loaded = list_leases(
        state
    )

    assert len(loaded) == 1

    assert (
        loaded[0].controller_status()
        is None
    )

    # Unknown ownership must never be
    # interpreted as definitely abandoned.
    abandoned = (
        find_abandoned_leases(
            state
        )
    )

    assert abandoned == []
    assert run_directory.exists()

    print(
        "UNKNOWN_OWNER_IDENTITY_"
        "FAIL_CLOSED_OK"
    )

    release_lease(
        sandbox_id,
        state,
    )
