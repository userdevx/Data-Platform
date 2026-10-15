from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from engine.sandbox.lifecycle.cleanup import CleanupStack
from engine.sandbox.process_identity import (
    process_identity_status,
    process_start_time,
)


_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_ID_PATTERN = re.compile(r"^dataworc-[a-z0-9-]+-[0-9a-f]{12}$")
LEASE_SCHEMA = "dataworc.sandbox.lease.v1"


def state_root() -> Path:
    """Persistent sandbox state (leases and run directories).

    Lives outside /tmp so a crash or reboot leaves a record that a
    doctor/cleanup pass can find.
    """

    configured = os.environ.get("DATAWORC_SANDBOX_STATE")

    if configured:
        return Path(configured)

    base = os.environ.get("XDG_STATE_HOME") or str(
        Path.home() / ".local" / "state"
    )

    return Path(base) / "dataworc" / "sandbox"


def new_sandbox_id(kind: str) -> str:
    if not _KIND_PATTERN.fullmatch(kind):
        raise ValueError(f"invalid sandbox kind: {kind!r}")

    return f"dataworc-{kind}-{uuid4().hex[:12]}"


def _validate_sandbox_id(sandbox_id: str) -> None:
    if not _ID_PATTERN.fullmatch(sandbox_id):
        raise ValueError(f"invalid sandbox id: {sandbox_id!r}")

def _atomic_write_json(path: Path, data: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass

        raise


@dataclass(frozen=True, slots=True)
class SandboxLease:
    sandbox_id: str
    runtime: str
    controller_pid: int
    controller_start_ticks: str | None
    created_at: str
    run_directory: str
    resources: tuple[str, ...] = field(default_factory=tuple)
    schema: str = LEASE_SCHEMA

    def to_dict(self) -> dict:
        data = asdict(self)
        data["resources"] = list(self.resources)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> SandboxLease:
        if data.get("schema") != LEASE_SCHEMA:
            raise ValueError(
                f"unsupported lease schema: {data.get('schema')!r}"
            )

        return cls(
            sandbox_id=data["sandbox_id"],
            runtime=data["runtime"],
            controller_pid=int(data["controller_pid"]),
            controller_start_ticks=data.get("controller_start_ticks"),
            created_at=data["created_at"],
            run_directory=data["run_directory"],
            resources=tuple(data.get("resources", ())),
        )

    def controller_status(self) -> bool | None:
        """Return live/dead/unknown for the recorded controller identity."""

        return process_identity_status(
            self.controller_pid,
            self.controller_start_ticks,
        )

    def controller_alive(self) -> bool:
        """Compatibility view that fails closed on unknown ownership.

        Unknown identity is treated as potentially live so automatic cleanup
        never deletes resources whose ownership cannot be established.
        """

        return self.controller_status() is not False


def _leases_directory(root: Path) -> Path:
    directory = root / "leases"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def _runs_directory(root: Path) -> Path:
    directory = root / "runs"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def write_lease(lease: SandboxLease, root: Path | None = None) -> Path:
    _validate_sandbox_id(lease.sandbox_id)
    path = _leases_directory(root or state_root()) / (
        f"{lease.sandbox_id}.json"
    )
    _atomic_write_json(path, lease.to_dict())
    os.chmod(path, 0o600)
    return path


def acquire_lease(
    sandbox_id: str,
    runtime: str,
    run_directory: Path,
    resources: tuple[str, ...] = (),
    root: Path | None = None,
) -> SandboxLease:
    pid = os.getpid()
    start_time = process_start_time(pid)

    if start_time is None:
        raise RuntimeError(
            "unable to establish sandbox controller process identity "
            f"for pid {pid}"
        )

    lease = SandboxLease(
        sandbox_id=sandbox_id,
        runtime=runtime,
        controller_pid=pid,
        controller_start_ticks=start_time,
        created_at=datetime.now(timezone.utc).isoformat(),
        run_directory=str(run_directory),
        resources=tuple(resources),
    )

    write_lease(lease, root)
    return lease


def release_lease(sandbox_id: str, root: Path | None = None) -> None:
    _validate_sandbox_id(sandbox_id)
    path = _leases_directory(root or state_root()) / f"{sandbox_id}.json"

    try:
        path.unlink()
    except FileNotFoundError:
        pass


def list_leases(root: Path | None = None) -> list[SandboxLease]:
    leases: list[SandboxLease] = []

    for path in sorted(_leases_directory(root or state_root()).glob(
        "dataworc-*.json"
    )):
        leases.append(
            SandboxLease.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        )

    return leases


def find_abandoned_leases(root: Path | None = None) -> list[SandboxLease]:
    """Return only leases whose recorded controller is definitely dead.

    Unknown/incomplete owner identities are preserved for manual recovery.
    """

    return [
        lease
        for lease in list_leases(root)
        if lease.controller_status() is False
    ]


@dataclass(frozen=True, slots=True)
class RunContext:
    sandbox_id: str
    run_directory: Path
    lease: SandboxLease


def provision_run(
    kind: str,
    cleanup: CleanupStack,
    root: Path | None = None,
    resources: tuple[str, ...] = (),
) -> RunContext:
    """Create a unique id, a private run directory and a lease.

    Teardown (delete the directory, then release the lease) is pushed
    onto ``cleanup`` so it runs even if the sandbox run fails. The lease
    is released last, so a crash mid-cleanup leaves it for the doctor.
    """

    state = root or state_root()
    sandbox_id = new_sandbox_id(kind)
    run_directory = _runs_directory(state) / sandbox_id
    run_directory.mkdir(mode=0o700)

    try:
        lease = acquire_lease(
            sandbox_id,
            kind,
            run_directory,
            resources,
            state,
        )
    except BaseException:
        shutil.rmtree(run_directory, ignore_errors=True)
        raise

    cleanup.add(
        lambda: release_lease(sandbox_id, state),
        name=f"release-lease:{sandbox_id}",
    )
    cleanup.add(
        lambda: shutil.rmtree(run_directory),
        name=f"remove-run-directory:{sandbox_id}",
    )

    return RunContext(
        sandbox_id=sandbox_id,
        run_directory=run_directory,
        lease=lease,
    )
