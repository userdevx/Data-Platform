from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from engine.intelligence.factory import IntelligenceFactory
from engine.intelligence.models import IntelligenceRequest
from engine.intelligence.validation.rule_validator import RuntimeRuleValidator
from engine.intelligence.search_learning import learn_from_public_search_result


DEFAULT_DEFINITION_PATH = "config/intelligence/active.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelligence",
        description="Process one request through the configurable Intelligence Runtime.",
    )

    parser.add_argument(
        "question",
        nargs="*",
        help="Request text to process.",
    )

    parser.add_argument(
        "--question",
        dest="question_flag",
        default="",
        help="Request text to process.",
    )

    parser.add_argument(
        "--definition",
        default=DEFAULT_DEFINITION_PATH,
        help="Path to the active intelligence definition.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full structured JSON response.",
    )

    parser.add_argument(
        "--source",
        default="cli",
        help="Source label for the request.",
    )

    parser.add_argument(
        "--conversation-id",
        default="",
        help="Stable identifier for the current conversation.",
    )

    return parser


def get_question(args: argparse.Namespace) -> str:
    if args.question_flag.strip():
        return args.question_flag.strip()

    return " ".join(args.question).strip()


def resolve_definition_path(root: Path, definition: str) -> Path:
    definition_path = Path(definition).expanduser()

    if not definition_path.is_absolute():
        definition_path = root / definition_path

    return definition_path.resolve()


def load_definition(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def print_payload(payload: dict[str, Any], exit_code: int) -> int:
    json_mode = "--json" in sys.argv

    if json_mode:
        print(json.dumps(payload))
        return exit_code

    answer = payload.get("answer")

    if isinstance(answer, str) and answer.strip():
        print(answer.strip())
        return exit_code

    print(json.dumps(payload))
    return exit_code


def print_cli_response(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload))
        return

    answer = payload.get("answer")

    if isinstance(answer, str) and answer.strip():
        print(answer.strip())
        return

    print("The request completed, but no answer was returned.")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    args = build_parser().parse_args()
    question = get_question(args)

    definition_path = resolve_definition_path(root, args.definition)

    try:
        definition = load_definition(definition_path)
    except Exception as error:
        return print_payload(
            {
                "status": "error",
                "answer": "The active intelligence definition could not be loaded.",
                "source": "intelligence_runtime",
                "capability": "definition_loader",
                "ability": "definition_loader",
                "data": {
                    "action": "Load active definition.",
                    "explanation": "The definition file is required before routing can begin.",
                    "next_step": "Check the active definition path.",
                },
                "errors": [str(error)],
            },
            1,
        )

    if not question:
        payload = {
            "status": "error",
            "answer": "Enter a request first.",
            "source": "intelligence_runtime",
            "capability": "request_validation",
            "ability": "request_validation",
            "data": {
                "action": "Rejected empty request.",
                "explanation": "A request must contain text before it can be routed.",
                "next_step": "Enter a request and run the command again.",
            },
            "errors": ["empty request"],
        }

        validator = RuntimeRuleValidator()
        return print_payload(
            validator.enforce_response(payload, definition),
            1,
        )

    try:
        factory = IntelligenceFactory(root=root)
        instance = factory.create(definition_path=definition_path)

        request_metadata: dict[str, Any] = {}

        if args.conversation_id.strip():
            request_metadata["conversation_id"] = (
                args.conversation_id.strip()
            )

        request = IntelligenceRequest.create(
            question=question,
            source=args.source,
            metadata=request_metadata,
        )

        response = instance.process(request)
        payload = response.to_dict()

        if (
            payload.get("capability") == "public_source_search"
            and payload.get("status") == "success"
        ):
            learning_result = learn_from_public_search_result(
                root=root,
                definition=definition,
                response_payload=payload,
            )

            payload.setdefault("data", {})["learning"] = learning_result

        validator = RuntimeRuleValidator()
        validated_payload = validator.enforce_response(payload, definition)

        exit_code = 0 if validated_payload.get("status") != "rejected" else 1

        return print_payload(validated_payload, exit_code)

    except Exception as error:
        payload = {
            "status": "error",
            "answer": "The Intelligence Runtime could not complete the request.",
            "source": "intelligence_runtime",
            "capability": "runtime_error",
            "ability": "runtime_error",
            "data": {
                "action": "Runtime execution failed.",
                "explanation": "The request reached the runtime but did not complete.",
                "next_step": "Review the error and correct the failing component.",
            },
            "errors": [str(error)],
        }

        validator = RuntimeRuleValidator()

        return print_payload(
            validator.enforce_response(payload, definition),
            1,
        )


if __name__ == "__main__":
    raise SystemExit(main())
