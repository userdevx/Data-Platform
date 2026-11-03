#!/usr/bin/env python3

import argparse
from datetime import datetime


APP_NAME = __APP_NAME__
REQUEST = __REQUEST__


def run_task(
    value: str,
) -> None:
    timestamp = datetime.now().isoformat(
        timespec="seconds",
    )

    print(
        "[",
        timestamp,
        "] ",
        APP_NAME,
        sep="",
    )

    print(
        "Request:",
        REQUEST,
    )

    print(
        "Input:",
        value,
    )

    print(
        "Automation completed.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=APP_NAME,
    )

    parser.add_argument(
        "--input",
        default="default",
    )

    args = parser.parse_args()

    run_task(
        args.input,
    )


if __name__ == "__main__":
    main()
