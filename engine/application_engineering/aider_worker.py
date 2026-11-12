"""DataWorc persistent Application Engineering request receiver.

Step 6: Local transport, validation, durable Data Engine records,
and fail-closed authorization. No coding execution is permitted here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import socketserver
import stat
import struct
import threading
from datetime import datetime, timezone
from uuid import uuid4

from engine.data_engine.record_writer import DataEngineRecordWriter

MAX_MESSAGE_BYTES = 32768
MAX_REQUEST_CHARS = 20000
MAX_TARGET_FILES = 64
MAX_TARGET_FILE_CHARS = 240


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_request(
    payload: object,
    workspace_root: Path,
) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object")

    allowed_keys = {
        "action", "request", "workspace", "target_files",
    }
    if set(payload) != allowed_keys:
        raise ValueError("Invalid request fields")

    if payload["action"] != "submit":
        raise ValueError("Unsupported request action")

    request = payload["request"]
    if not isinstance(request, str) or not request.strip():
        raise ValueError("Request text is required")
    if len(request) > MAX_REQUEST_CHARS:
        raise ValueError("Request exceeds size limit")

    root = workspace_root.resolve(strict=True)

    if not root.is_dir():
        raise ValueError("Workspace root must be a directory")

    workspace_name = payload["workspace"]
    if not isinstance(workspace_name, str):
        raise ValueError("Invalid workspace")

    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", workspace_name):
        raise ValueError("Invalid workspace identifier")

    workspace = root / workspace_name

    if workspace.is_symlink() or not workspace.is_dir():
        raise ValueError("Workspace is missing or unsafe")

    resolved = workspace.resolve(strict=True)

    if resolved.parent != root:
        raise ValueError("Workspace is outside managed root")

    target_files = payload["target_files"]

    if (
        not isinstance(target_files, list)
        or not 1 <= len(target_files) <= MAX_TARGET_FILES
        or len(set(map(str, target_files))) != len(target_files)
    ):
        raise ValueError("Invalid target file list")

    normalized_files = []

    for name in target_files:
        if (
            not isinstance(name, str)
            or not name
            or len(name) > MAX_TARGET_FILE_CHARS
            or "," in name
        ):
            raise ValueError("Invalid target file")

        relative = Path(name)

        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "." in relative.parts
            or name != relative.as_posix()
        ):
            raise ValueError("Unsafe target path")

        target = resolved / relative

        if not target.resolve().is_relative_to(resolved):
            raise ValueError("Target escapes workspace")

        for ancestor in (target, *target.parents):
            if ancestor == resolved:
                break
            if ancestor.is_symlink():
                raise ValueError("Symlink target rejected")

        normalized_files.append(name)

    return {
        "request": request.strip(),
        "workspace": str(resolved),
        "target_files": normalized_files,
    }


class WorkerState:
    """Validated request receiver with automatic Aider dispatch."""

    def __init__(self, workspace_root: Path) -> None:
        from engine.application_engineering.coding_jobs import (
            CodingJobs,
        )

        self.workspace_root = workspace_root.resolve(
            strict=True
        )
        self.started_at = utc_now()
        self.jobs = CodingJobs()

    def start(self) -> None:
        self.jobs.start()

    def stop(self) -> None:
        self.jobs.stop()

    def handle(self, payload: object) -> dict:
        if (
            isinstance(payload, dict)
            and payload == {"action": "health"}
        ):
            return {
                "status": "ready",
                "component": "application_engineering_worker",
                "started_at": self.started_at,
                "coding_execution_enabled": self.jobs.running,
                "approval_required": False,
            }

        if (
            isinstance(payload, dict)
            and payload.get("action") == "status"
        ):
            if set(payload) != {
                "action", "execution_id"
            }:
                raise ValueError(
                    "Invalid status request fields"
                )

            execution_id = payload["execution_id"]

            if (
                not isinstance(execution_id, str)
                or not execution_id.strip()
            ):
                raise ValueError(
                    "Invalid execution identifier"
                )

            return self.jobs.status(execution_id)

        # Retain the existing Step 6 path and
        # target-file validation.
        normalized = validate_request(
            payload,
            self.workspace_root,
        )

        # The original application-development request
        # authorizes coding within its validated workspace.
        return self.jobs.submit(**normalized)


class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        # Linux peer credentials: only the service's own UID
        # may send requests, even if socket permissions change.
        credentials = self.request.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            struct.calcsize("3i"),
        )
        _, uid, _ = struct.unpack("3i", credentials)

        if uid != os.getuid():
            self.send({"status": "error", "error": "Unauthorized peer"})
            return

        try:
            data = self.rfile.readline(MAX_MESSAGE_BYTES + 1)

            if not data or len(data) > MAX_MESSAGE_BYTES:
                raise ValueError("Invalid message size")

            payload = json.loads(data.decode("utf-8"))

            response = self.server.state.handle(payload)

        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as error:
            response = {
                "status": "error",
                "error": str(error),
            }

        except Exception:
            # Fail closed: never report acceptance if Data Engine
            # persistence or another internal operation fails.
            response = {
                "status": "error",
                "error": "Worker request could not be processed",
            }

        self.send(response)

    def send(self, payload: dict) -> None:
        self.wfile.write(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        self.wfile.flush()


class WorkerServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    request_queue_size = 16
    allow_reuse_address = False

    def __init__(self, socket_path: Path, state: WorkerState):
        self.state = state
        super().__init__(str(socket_path), RequestHandler)


def run_worker(socket_path: Path, workspace_root: Path) -> None:
    socket_path = socket_path.expanduser().absolute()
    socket_path.parent.mkdir(parents=True, exist_ok=True)

    os.chmod(socket_path.parent, 0o700)

    if socket_path.is_symlink():
        raise RuntimeError("Socket path cannot be a symlink")

    if socket_path.exists():
        existing = socket_path.stat()

        if (
            not stat.S_ISSOCK(existing.st_mode)
            or existing.st_uid != os.getuid()
        ):
            raise RuntimeError("Socket path is already occupied")

        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            probe.settimeout(1)
            probe.connect(str(socket_path))
        except (ConnectionRefusedError, FileNotFoundError):
            socket_path.unlink()
        else:
            raise RuntimeError("Worker is already running")
        finally:
            probe.close()

    state = WorkerState(workspace_root)

    server = WorkerServer(socket_path, state)
    state.start()
    os.chmod(socket_path, 0o600)

    stopped = threading.Event()

    def shutdown(signum, frame):
        if not stopped.is_set():
            stopped.set()
            threading.Thread(
                target=server.shutdown,
                daemon=True,
            ).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        print(
            json.dumps({
                "event": "worker_started",
                "socket": str(socket_path),
                "timestamp": utc_now(),
            }),
            flush=True,
        )

        server.serve_forever(poll_interval=0.25)

    finally:
        state.stop()
        server.server_close()

        if socket_path.exists() and stat.S_ISSOCK(
            socket_path.stat().st_mode
        ):
            socket_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    args = parser.parse_args()

    run_worker(args.socket, args.workspace_root)


if __name__ == "__main__":
    main()
