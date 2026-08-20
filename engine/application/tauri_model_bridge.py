from __future__ import annotations

import argparse
import json
import sys

from engine.application.model_options_action import (
    get_model_options,
)
from engine.application.model_request_action import (
    process_manual_model_request,
)
from services.visual_model.provider_errors import (
    VisualProviderError,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Application model-selection bridge."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "options",
        help="Return runtime model options.",
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="Send a real request to a selected model.",
    )

    ask_parser.add_argument(
        "--option-id",
        required=True,
    )

    ask_parser.add_argument(
        "--question",
        required=True,
    )

    ask_parser.add_argument(
        "--capability",
        default="",
    )

    ask_parser.add_argument(
        "--arguments-json",
        default="{}",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        if arguments.command == "options":
            result = get_model_options()
        else:
            request_arguments = json.loads(
                arguments.arguments_json
            )

            if not isinstance(
                request_arguments,
                dict,
            ):
                raise ValueError(
                    "Model request arguments "
                    "must be a JSON object."
                )

            result = process_manual_model_request(
                question=arguments.question,
                option_id=arguments.option_id,
                capability=arguments.capability,
                arguments=request_arguments,
            )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
            )
        )

        return (
            0
            if result.get("status") == "success"
            else 1
        )

    except (
        OSError,
        ValueError,
        VisualProviderError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "models": [],
                    "errors": [
                        str(error),
                    ],
                },
                ensure_ascii=False,
            )
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
