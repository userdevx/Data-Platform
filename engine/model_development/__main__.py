from __future__ import annotations

import argparse
import json
from typing import Any

from engine.model_development.runtime import (
    discover_base_models,
    inspect_base_model,
    test_base_model,
)


def _print_json(
    value: Any,
) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=(
            "python -m "
            "engine.model_development"
        ),
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser(
        "list"
    )

    inspect_parser = (
        commands.add_parser(
            "inspect"
        )
    )

    inspect_parser.add_argument(
        "--model",
        required=True,
    )

    test_parser = (
        commands.add_parser(
            "test"
        )
    )

    test_parser.add_argument(
        "--model",
        required=True,
    )

    test_parser.add_argument(
        "--prompt",
        required=True,
    )

    test_parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
    )

    test_parser.add_argument(
        "--output",
        default=None,
    )

    test_parser.add_argument(
        "--steps",
        type=int,
        default=6,
    )

    test_parser.add_argument(
        "--width",
        type=int,
        default=384,
    )

    test_parser.add_argument(
        "--height",
        type=int,
        default=384,
    )

    test_parser.add_argument(
        "--seed",
        type=int,
        default=17,
    )

    arguments = (
        parser.parse_args()
    )

    if arguments.command == "list":
        models = (
            discover_base_models()
        )

        _print_json(
            {
                "base_models": [
                    {
                        "name": model.name,
                        "path": str(
                            model.path
                        ),
                        "model_type": (
                            model.model_type
                        ),
                        "capability": (
                            model.capability
                        ),
                        "runtime_format": (
                            model.runtime_format
                        ),
                    }
                    for model
                    in models
                ],
                "count": len(
                    models
                ),
            }
        )

        return

    if arguments.command == "inspect":
        _print_json(
            inspect_base_model(
                arguments.model
            )
        )
        return

    if arguments.command == "test":
        _print_json(
            test_base_model(
                arguments.model,
                arguments.prompt,
                max_new_tokens=(
                    arguments.max_new_tokens
                ),
                output_path=(
                    arguments.output
                ),
                inference_steps=(
                    arguments.steps
                ),
                width=arguments.width,
                height=arguments.height,
                seed=arguments.seed,
            )
        )
        return

    raise RuntimeError(
        "Unsupported command."
    )


if __name__ == "__main__":
    main()
