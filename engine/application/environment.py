from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

ENVIRONMENT_PATH = PROJECT_ROOT / ".env"


def load_project_environment() -> None:
    """Load project environment variables without replacing active values."""

    if not ENVIRONMENT_PATH.exists():
        return

    for raw_line in ENVIRONMENT_PATH.read_text(
        encoding="utf-8",
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        name, value = line.split(
            "=",
            1,
        )

        name = name.strip()
        value = value.strip()

        if not name:
            continue

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        os.environ.setdefault(
            name,
            value,
        )
