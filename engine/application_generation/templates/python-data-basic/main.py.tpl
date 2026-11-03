#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


APP_NAME = __APP_NAME__
REQUEST = __REQUEST__


def inspect_csv(
    path: Path,
) -> None:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.reader(
            handle,
        )

        try:
            header = next(
                reader,
            )
        except StopIteration:
            print(
                "CSV file is empty.",
            )
            return

        row_count = sum(
            1
            for _ in reader
        )

    print(APP_NAME)
    print(REQUEST)
    print()
    print(
        "File:",
        path,
    )
    print(
        "Rows:",
        row_count,
    )
    print(
        "Columns:",
        len(header),
    )
    print(
        "Column names:",
    )

    for column in header:
        print(
            " -",
            column,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=APP_NAME,
    )

    parser.add_argument(
        "csv_file",
        type=Path,
    )

    args = parser.parse_args()

    inspect_csv(
        args.csv_file,
    )


if __name__ == "__main__":
    main()
