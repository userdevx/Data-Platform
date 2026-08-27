from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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


from engine.realtime.query import (
    RealTimeQueryService,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Query historical real-time system "
            "observations stored in the Data Engine."
        )
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help=(
            "Return only the latest persisted "
            "system snapshot."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Maximum number of historical records "
            "to return. Default: 10."
        ),
    )

    parser.add_argument(
        "--start-at",
        default=None,
        help=(
            "Optional inclusive ISO-8601 lower "
            "timestamp boundary."
        ),
    )

    parser.add_argument(
        "--end-at",
        default=None,
        help=(
            "Optional inclusive ISO-8601 upper "
            "timestamp boundary."
        ),
    )

    return parser.parse_args()


def validate_arguments(
    arguments: argparse.Namespace,
) -> None:
    if arguments.limit < 1:
        raise ValueError(
            "--limit must be at least 1."
        )


def main() -> int:
    arguments = parse_arguments()

    try:
        validate_arguments(
            arguments
        )

        service = RealTimeQueryService()

        if arguments.latest:
            record = (
                service.latest_system_snapshot()
            )

            print(
                json.dumps(
                    {
                        "mode": "latest",
                        "record": record,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )

            return 0

        records = (
            service.system_snapshot_history(
                limit=arguments.limit,
                start_at=arguments.start_at,
                end_at=arguments.end_at,
            )
        )

        print(
            json.dumps(
                {
                    "mode": "history",
                    "count": len(records),
                    "records": records,
                },
                indent=2,
                sort_keys=True,
            )
        )

        return 0

    except (
        TypeError,
        ValueError,
    ) as exc:
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
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
