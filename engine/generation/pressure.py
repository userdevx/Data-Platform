"""Pressure Stall Information, for admission decisions.

Instantaneous CPU percentage is the wrong input: one core at 100% may
be a compile that ends in two seconds. PSI reports how long tasks
actually stalled waiting for a resource, which is what "the machine is
too busy to start this" really means.

`some avg10` is the field to admit on. Where PSI is unavailable the
reading is unknown, and unknown admits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PRESSURE_ROOT = Path("/proc/pressure")


@dataclass(frozen=True)
class PressureSnapshot:
    cpu_some_avg10: float | None
    memory_some_avg10: float | None
    io_some_avg10: float | None
    available: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def exceeds(
        self,
        *,
        cpu: float,
        memory: float,
        io: float,
    ) -> bool:
        if not self.available:
            return False

        pairs = (
            (self.cpu_some_avg10, cpu),
            (self.memory_some_avg10, memory),
            (self.io_some_avg10, io),
        )

        return any(
            value is not None and value > limit
            for value, limit in pairs
        )


def _read_some_avg10(name: str) -> float | None:
    path = PRESSURE_ROOT / name

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in content.splitlines():
        if not line.startswith("some "):
            continue

        for field in line.split():
            key, _, value = field.partition("=")

            if key == "avg10":
                try:
                    return float(value)
                except ValueError:
                    return None

    return None


def read_pressure() -> PressureSnapshot:
    cpu = _read_some_avg10("cpu")
    memory = _read_some_avg10("memory")
    io = _read_some_avg10("io")

    return PressureSnapshot(
        cpu_some_avg10=cpu,
        memory_some_avg10=memory,
        io_some_avg10=io,
        available=any(v is not None for v in (cpu, memory, io)),
    )
