from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from threading import Event


REPOSITORY_ROOT = Path(
    __file__
).resolve().parents[1]

if str(
    REPOSITORY_ROOT
) not in sys.path:
    sys.path.insert(
        0,
        str(
            REPOSITORY_ROOT
        ),
    )


from engine.realtime.system_source import (
    SystemRuntimeSource,
)
from engine.realtime.worker import (
    RealTimeCollectionWorker,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect real operating-system runtime "
            "observations and persist them through "
            "the Data Engine."
        )
    )

    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=30.0,
        help=(
            "Seconds between collection attempts. "
            "Default: 30."
        ),
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help=(
            "Maximum number of collection attempts. "
            "If omitted, collection continues until "
            "SIGINT or SIGTERM."
        ),
    )

    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=5,
        help=(
            "Stop after this many consecutive "
            "collection failures. Default: 5."
        ),
    )

    return parser.parse_args()


def validate_arguments(
    arguments: argparse.Namespace,
) -> None:
    if arguments.interval_seconds < 0:
        raise ValueError(
            "--interval-seconds cannot be negative."
        )

    if (
        arguments.iterations is not None
        and arguments.iterations < 1
    ):
        raise ValueError(
            "--iterations must be at least 1."
        )

    if (
        arguments.max_consecutive_failures
        < 1
    ):
        raise ValueError(
            "--max-consecutive-failures "
            "must be at least 1."
        )


def install_signal_handlers(
    stop_event: Event,
) -> None:
    def handle_signal(
        signum: int,
        frame,
    ) -> None:
        del frame

        print(
            json.dumps(
                {
                    "event": "shutdown_requested",
                    "signal": signum,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        stop_event.set()

    signal.signal(
        signal.SIGINT,
        handle_signal,
    )

    signal.signal(
        signal.SIGTERM,
        handle_signal,
    )


def main() -> int:
    arguments = parse_arguments()

    try:
        validate_arguments(
            arguments
        )
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "status": "invalid_arguments",
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )

        return 2

    stop_event = Event()

    install_signal_handlers(
        stop_event
    )

    source = SystemRuntimeSource()

    worker = RealTimeCollectionWorker(
        source=source,
        interval_seconds=(
            arguments.interval_seconds
        ),
        max_consecutive_failures=(
            arguments.max_consecutive_failures
        ),
    )

    print(
        json.dumps(
            {
                "event": "worker_started",
                "interval_seconds": (
                    arguments.interval_seconds
                ),
                "iterations": (
                    arguments.iterations
                ),
                "max_consecutive_failures": (
                    arguments.max_consecutive_failures
                ),
                "source": (
                    type(source).__name__
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    try:
        result = worker.run(
            iterations=arguments.iterations,
            stop_event=stop_event,
        )

    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": (
                        type(exc).__name__
                    ),
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )

        return 1

    print(
        json.dumps(
            {
                "status": "completed",
                **result,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
