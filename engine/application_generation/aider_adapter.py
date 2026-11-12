"""Bounded, containerized Aider code-editing backend for DataWorc V1B.

This is an opt-in coding-agent adapter. It is NOT yet wired to
ApplicationGenerationCapability or ApplicationEngineeringRuntime.
Runs Aider with Podman against a single, verified generated-application
workspace. Only Application Engineering may approve acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import signal
import sys
import tempfile
import time
from uuid import uuid4
from urllib.parse import urlparse


def in_root(path: Path, root: Path) -> bool:
    root = root.resolve(strict=True)
    path = path.resolve(strict=True)
    return path != root and root in path.parents


def inventory(workspace: Path) -> dict[str, str]:
    """Hash regular files without following symlinks or reading outside the workspace."""
    result: dict[str, str] = {}
    for directory, dirs, files in os.walk(workspace, followlinks=False):
        parent = Path(directory)
        for name in [*dirs, *files]:
            p = parent / name
            if p.is_symlink():
                raise ValueError(f"Symlink rejected in agent workspace: {p}")
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            p = parent / name
            if not p.is_file():
                raise ValueError(f"Non-file rejected: {p}")
            if p.stat().st_size > 4 * 1024 * 1024:
                raise ValueError(f"Oversized file rejected in agent workspace: {p}")
            result[str(p.relative_to(workspace))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def classify_changes(before: dict[str, str], after: dict[str, str],
                     allowed: list[str]) -> tuple[list[str], list[str]]:
    """Return all changed paths and paths outside the explicit edit allowlist."""
    changed = sorted(name for name in before.keys() | after.keys()
                     if before.get(name) != after.get(name))
    unexpected = sorted(set(changed) - set(allowed))
    return changed, unexpected


def relative_file(workspace: Path, file_name: str) -> str:
    path = Path(file_name)
    if path.is_absolute() or ".." in path.parts or not path.parts or "," in file_name:
        raise ValueError(f"Unsafe agent file: {file_name}")
    target = workspace / path
    # Prevent symlink traversal through any existing parent.
    for ancestor in (target, *target.parents):
        if ancestor == workspace.parent:
            break
        if ancestor.is_symlink():
            raise ValueError(f"Symlink rejected: {ancestor}")
    if not target.resolve().is_relative_to(workspace.resolve()):
        raise ValueError(f"File escapes workspace: {file_name}")
    return path.as_posix()


def make_command(*, workspace: Path, model: str, base: str, image: str,
                 prompt_name: str, files: list[str], container_name: str) -> list[str]:
    if not model or any(ch.isspace() for ch in model) or "/" in model:
        raise ValueError("Model must be an installed Ollama model tag")
    endpoint = urlparse(base)
    if (endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost")
            or endpoint.port is None or endpoint.username is not None
            or endpoint.password is not None or endpoint.path not in ("", "/")
            or endpoint.query or endpoint.fragment):
        raise ValueError("PoC requires a plain loopback Ollama HTTP endpoint")
    if not image or "," in str(workspace):
        raise ValueError("Container image or workspace path not usable")
    args = [
        "podman", "run", "--rm", "--name", container_name,
        "--pull=never", "--network=host",
        "--cap-drop=all", "--security-opt=no-new-privileges",
        "--read-only", "--pids-limit=128", "--memory=1536m", "--cpus=2",
        "--userns=keep-id", "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=96m",
        "--mount", f"type=bind,src={workspace},dst=/app,rw",
        "--workdir", "/app", "--env", "HOME=/tmp",
        "--env", f"OLLAMA_API_BASE={base}",
        image,
        "--model", f"ollama_chat/{model}",
        "--message-file", f"/app/{prompt_name}",
        "--no-git", "--no-auto-commits", "--no-dirty-commits",
        "--no-auto-test", "--no-auto-lint", "--no-suggest-shell-commands",
        "--no-analytics", "--no-check-update", "--no-restore-chat-history",
        "--no-gitignore", "--no-detect-urls",
        "--config", "/app/.dataworc-agent-config.yml", "--env-file", "/dev/null",
        "--input-history-file", "/tmp/.aider.input.history",
        "--chat-history-file", "/tmp/.aider.chat.history.md",
        "--llm-history-file", "/tmp/.aider.llm.history",
        "--no-pretty", "--no-stream", "--map-tokens", "0",
        "--timeout", "300", "--edit-format", "whole",
    ]
    for file_name in files:
        args.extend(("--file", f"/app/{file_name}"))
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ollama-base", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--file", action="append", dest="files", required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.workspace_root.resolve(strict=True)
    workspace = args.workspace.resolve(strict=True)
    if not in_root(workspace, root) or args.seconds < 30 or args.seconds > 1200:
        parser.error("Invalid managed workspace or time limit")
    if not args.request_file.is_file():
        parser.error("Request file does not exist")
    if args.audit.resolve() == workspace or workspace in args.audit.resolve().parents:
        parser.error("Audit must be outside the agent workspace")
    files = [relative_file(workspace, name) for name in args.files]
    before = inventory(workspace)
    container_name = "dataworc-aider-" + uuid4().hex[:12]
    command = make_command(workspace=workspace, model=args.model,
                           base=args.ollama_base, image=args.image,
                           prompt_name=".dataworc-agent-request.txt", files=files,
                           container_name=container_name)
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "command": command,
                          "existing_files": sorted(before)}, indent=2))
        return 0
    if shutil.which("podman") is None:
        parser.error("Podman is not installed")
    # Aider's image must already have been pulled; never pull an image mid-build.
    subprocess.run(["podman", "image", "exists", args.image], check=True)
    for name in files:
        p = workspace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)
    before = inventory(workspace)  # Account for adapter-created empty placeholders.
    request = workspace / ".dataworc-agent-request.txt"
    if request.exists() or request.is_symlink():
        parser.error("Temporary request path already exists")
    config = workspace / ".dataworc-agent-config.yml"
    if config.exists() or config.is_symlink():
        parser.error("Temporary Aider config path already exists")
    args.audit.mkdir(parents=True, exist_ok=True)
    config.write_text("{}\n", encoding="utf-8")
    request.write_text(args.request_file.read_text(encoding="utf-8") +
                       "\nOnly edit the provided files. Do not request shell commands.\n",
                       encoding="utf-8")
    started = time.monotonic()
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def handle_sigterm(signum, _frame):
        raise InterruptedError(
            f"Aider execution received signal {signum}"
        )

    def remove_execution_container(log):
        # This name belongs only to the current adapter invocation.
        # Never target the persistent Aider service container.
        subprocess.run(
            ["podman", "rm", "--force", container_name],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=25,
            check=False,
        )

        probe = subprocess.run(
            ["podman", "container", "exists", container_name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )

        if probe.returncode == 0:
            raise RuntimeError(
                "Temporary execution container survived cleanup"
            )

        if probe.returncode != 1:
            raise RuntimeError(
                "Could not verify temporary container removal"
            )

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        with (args.audit / "aider.log").open(
            "w", encoding="utf-8"
        ) as log:
            try:
                completed = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=args.seconds,
                    check=False,
                )
                rc = completed.returncode
                timed_out = False

            except subprocess.TimeoutExpired:
                rc = 124
                timed_out = True
                signal.signal(
                    signal.SIGTERM,
                    previous_sigterm,
                )
                remove_execution_container(log)

            except BaseException:
                signal.signal(
                    signal.SIGTERM,
                    previous_sigterm,
                )
                remove_execution_container(log)
                raise

    finally:
        signal.signal(
            signal.SIGTERM,
            previous_sigterm,
        )

        config_valid = (
            not config.is_symlink()
            and config.is_file()
            and config.read_text(encoding="utf-8") == "{}\\n"
        )

        request.unlink(missing_ok=True)
        config.unlink(missing_ok=True)

    after = inventory(workspace)
    changes, unexpected = classify_changes(before, after, files)
    edited_targets = [name for name in files if name in changes and
                      (workspace / name).is_file() and
                      (workspace / name).stat().st_size > 0]
    report = {
        "coding_agent": "aider", "model": args.model,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "exit_code": rc, "timed_out": timed_out,
        "files_changed": changes,
        "unexpected_changes": unexpected,
        "config_integrity": config_valid,
        "edited_target_files": edited_targets,
        "agent_execution_success": rc == 0 and bool(edited_targets) and not unexpected and config_valid,
        "engineering_verified": False,
        "notice": "Application Engineering compile/test/gVisor verification still required",
    }
    (args.audit / "aider-result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report["agent_execution_success"] else 1


if __name__ == "__main__":
    sys.exit(main())
