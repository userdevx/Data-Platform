from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.intelligence.factory import IntelligenceFactory
from engine.intelligence.models import IntelligenceRequest
from engine.intelligence.validation.rule_validator import RuntimeRuleValidator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = PROJECT_ROOT / "engine" / "agents"

INPUT_FILE = AGENT_DIR / "agent_input.json"
OUTPUT_FILE = AGENT_DIR / "agent_output.json"
LOG_FILE = AGENT_DIR / "agent.log"
DEFAULT_DEFINITION_FILE = PROJECT_ROOT / "config" / "intelligence" / "active.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    AGENT_DIR.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{utc_now()} {message}\n")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        raw = path.read_text(encoding="utf-8").strip()

        if not raw:
            return None

        payload = json.loads(raw)

        if isinstance(payload, dict):
            return payload

        return {
            "question": str(payload),
        }

    except Exception as error:
        return {
            "question": "",
            "error": f"Could not read input JSON: {error}",
        }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def normalize_question(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""

    for key in ("question", "input", "prompt", "query", "text"):
        value = payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def resolve_definition_path(payload: dict[str, Any] | None) -> Path:
    if payload:
        raw_path = payload.get("definition_path")

        if isinstance(raw_path, str) and raw_path.strip():
            candidate = Path(raw_path.strip())

            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate

            return candidate

    return DEFAULT_DEFINITION_FILE


def build_error_response(
    *,
    message: str,
    source: str = "intelligence_worker",
    details: str | None = None,
) -> dict[str, Any]:
    errors = []

    if details:
        errors.append(details)

    return {
        "status": "error",
        "answer": message,
        "source": source,
        "capability": "worker_error",
        "ability": "worker_error",
        "created_at": utc_now(),
        "data": {
            "action": "Worker request failed.",
            "explanation": "The request reached the generic intelligence worker but could not be completed.",
            "next_step": "Review the worker input, runtime configuration, and validation output.",
        },
        "errors": errors,
    }


def process_once() -> dict[str, Any]:
    payload = read_json(INPUT_FILE)

    if payload and payload.get("error"):
        return build_error_response(
            message="The worker could not read the request input.",
            details=str(payload.get("error")),
        )

    question = normalize_question(payload)

    if not question:
        return build_error_response(
            message="Enter a question before submitting to the Intelligence Runtime.",
        )

    definition_path = resolve_definition_path(payload)

    if not definition_path.exists():
        return build_error_response(
            message="The active intelligence definition could not be found.",
            details=str(definition_path),
        )

    definition = json.loads(definition_path.read_text(encoding="utf-8"))

    factory = IntelligenceFactory(root=PROJECT_ROOT)
    instance = factory.create(definition_path=definition_path)

    request = IntelligenceRequest.create(
        question=question,
        source="agent_worker",
    )

    response = instance.process(request)
    response_payload = response.to_dict()

    validator = RuntimeRuleValidator()
    validated_payload = validator.enforce_response(response_payload, definition)

    return validated_payload


def run_forever(poll_seconds: float = 1.0) -> None:
    log("Generic intelligence worker started.")

    last_seen_input = ""

    while True:
        try:
            current_input = INPUT_FILE.read_text(encoding="utf-8") if INPUT_FILE.exists() else ""

            if current_input and current_input != last_seen_input:
                last_seen_input = current_input

                result = process_once()
                write_json(OUTPUT_FILE, result)

                status = result.get("status", "unknown")
                log(f"Request processed with status={status}.")

        except KeyboardInterrupt:
            log("Generic intelligence worker stopped.")
            raise

        except Exception as error:
            result = build_error_response(
                message="The Intelligence Runtime failed safely.",
                details=str(error),
            )
            write_json(OUTPUT_FILE, result)
            log(f"Worker error: {error}")

        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
