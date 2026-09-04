from __future__ import annotations

import argparse
import json
import sys

from engine.application.model_options_action import (
    get_model_options,
)
from engine.generation.bindings import (
    build_job_record_store,
)
from engine.generation.service import (
    GenerationJobService,
)
from engine.application.model_request_action import (
    process_manual_model_request,
)
from engine.application.local_model_action import (
    MODEL_PYTHON,
    PROJECT_ROOT,
)
from engine.application.local_model_worker import (
    worker_runtime_identity,
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

    subparsers.add_parser(
        "runtime-identity",
        help=(
            "Return local model worker "
            "runtime identity."
        ),
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

    ask_parser.add_argument(
        "--request-id",
        default="",
    )

    cancel_parser = subparsers.add_parser(
        "cancel-generation",
        help=(
            "Cancel generation work for "
            "one application request."
        ),
    )

    cancel_parser.add_argument(
        "--request-id",
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        if arguments.command == "options":
            result = get_model_options()

        elif (
            arguments.command
            == "runtime-identity"
        ):
            result = worker_runtime_identity(
                model_python=MODEL_PYTHON,
                project_root=PROJECT_ROOT,
            )

        elif (
            arguments.command
            == "cancel-generation"
        ):
            service = GenerationJobService(
                store=build_job_record_store(),
                project_root=PROJECT_ROOT,
            )

            cancelled = service.cancel_request(
                arguments.request_id
            )

            result = {
                "status": "success",
                "request_id": (
                    arguments.request_id
                ),
                "cancelled_count": len(
                    cancelled
                ),
                "cancelled_job_ids": [
                    job.job_id
                    for job in cancelled
                ],
            }

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
                request_id=(
                    arguments.request_id
                ),
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
