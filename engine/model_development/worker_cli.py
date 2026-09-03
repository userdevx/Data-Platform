from __future__ import annotations

import argparse
import json
import sys
from typing import Any


from engine.model_development.image_runtime import (
    worker_runtime_identity,
)
from engine.model_development.runtime import (
    test_base_model,
)


def _print_json(
    value: dict[str, Any],
) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
        )
    )


def build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "python -m "
            "engine.model_development."
            "worker_cli"
        )
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser(
        "identity"
    )

    execute = commands.add_parser(
        "execute"
    )

    execute.add_argument(
        "--model",
        required=True,
    )

    execute.add_argument(
        "--prompt",
        required=True,
    )

    execute.add_argument(
        "--max-new-tokens",
        type=int,
        default=128,
    )

    execute.add_argument(
        "--steps",
        type=int,
        default=8,
    )

    execute.add_argument(
        "--width",
        type=int,
        default=256,
    )

    execute.add_argument(
        "--height",
        type=int,
        default=256,
    )

    execute.add_argument(
        "--seed",
        type=int,
        default=17,
    )

    execute.add_argument(
        "--output",
        default=None,
    )

    return parser


def main() -> int:
    arguments = (
        build_parser()
        .parse_args()
    )

    try:
        if (
            arguments.command
            == "identity"
        ):
            _print_json(
                {
                    "status": "success",
                    "runtime_identity": (
                        worker_runtime_identity()
                    ),
                }
            )

            return 0

        result = test_base_model(
            arguments.model,
            arguments.prompt,
            max_new_tokens=(
                arguments
                .max_new_tokens
            ),
            output_path=(
                arguments.output
            ),
            inference_steps=(
                arguments.steps
            ),
            width=(
                arguments.width
            ),
            height=(
                arguments.height
            ),
            seed=(
                arguments.seed
            ),
        )

        _print_json(
            {
                "status": "success",
                **result,
            }
        )

        return 0

    except Exception as error:
        _print_json(
            {
                "status": "error",
                "errors": [
                    str(error)
                ],
            }
        )

        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )
