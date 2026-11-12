"""Configuration-driven coding-agent dispatcher for DataWorc.

Reads provider, model, container, and execution parameters strictly from
active platform configuration and validates agent execution output against
the generated audit evidence. Compilation, testing, and sandbox safety
verification remain the sole responsibility of Application Engineering.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def dispatch_coding_agent(
    *,
    project_root: Path,
    workspace: Path,
    request: str,
    target_files: list[str],
) -> Optional[dict]:
    """Resolves active configuration and executes the configured coding agent adapter."""
    # 1. Inspect Intelligence Ability Gate
    intel_config_path = project_root / "config/intelligence/active.json"
    if not intel_config_path.is_file():
        return None

    try:
        intel_config = json.loads(intel_config_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    enabled_abilities = intel_config.get("abilities", {}).get("enabled", [])
    if "application_generation" not in enabled_abilities:
        return None

    provider = intel_config.get("provider", {})
    if not provider.get("enabled"):
        return None

    model_name = provider.get("model")
    if not model_name:
        return None

    # 2. Inspect Coding Agent Execution Profile
    profile_path = project_root / "config/application_generation/coding_agent.json"
    if not profile_path.is_file():
        return None

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not profile.get("enabled", False):
        return None

    container_image = profile.get("container_image")
    ollama_base = os.environ.get("OLLAMA_API_BASE") or profile.get("endpoint", "http://127.0.0.1:11434")
    seconds = str(profile.get("seconds", 300))

    # 3. Locate Adapter Script
    adapter_path = project_root / "engine/application_generation/aider_adapter.py"
    if not adapter_path.is_file():
        return None

    # 4. Prepare Language-Agnostic Directive
    directive = (
        f"Implement the requested application requirements directly in the target files.\n"
        f"Requirements: {request.strip()}\n"
    )

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as req_file:
        req_file.write(directive)
        req_path = Path(req_file.name)

    audit_dir = Path(tempfile.mkdtemp(prefix="dataworc-agent-audit-"))

    try:
        cmd = [
            str(project_root / "venv/bin/python"),
            str(adapter_path),
            "--workspace-root", str(workspace.parent.resolve()),
            "--workspace", str(workspace.resolve()),
            "--request-file", str(req_path),
            "--model", model_name,
            "--ollama-base", ollama_base,
            "--image", container_image,
            "--audit", str(audit_dir),
            "--seconds", seconds,
        ]
        for file_name in target_files:
            cmd.extend(["--file", file_name])

        proc = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=int(seconds) + 30,
        )

        result_path = audit_dir / "aider-result.json"

        # If execution fails at the subprocess level
        if proc.returncode != 0:
            return {
                "exit_code": proc.returncode,
                "agent_execution_success": False,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "audit_dir": str(audit_dir),
            }

        # Validate audit evidence produced by adapter
        if result_path.is_file():
            try:
                result_data = json.loads(result_path.read_text(encoding="utf-8"))
                result_data["exit_code"] = 0
                result_data["audit_dir"] = str(audit_dir)
                return result_data
            except Exception:
                pass

        return {
            "exit_code": 1,
            "agent_execution_success": False,
            "error": "Missing or unparseable aider-result.json audit evidence",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "audit_dir": str(audit_dir),
        }

    except Exception as exc:
        return {
            "exit_code": 1,
            "agent_execution_success": False,
            "error": str(exc),
            "audit_dir": str(audit_dir),
        }
    finally:
        if req_path.is_file():
            req_path.unlink(missing_ok=True)
