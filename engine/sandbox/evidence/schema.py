from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


EVIDENCE_SCHEMA = "dataworc.sandbox.evidence.v1"
ANCHOR_SCHEMA = "dataworc.sandbox.evidence_anchor.v1"

GENESIS_HASH = "0" * 64


class EvidenceSchemaError(ValueError):
    pass


def validate_json_value(
    value: Any,
    *,
    path: str = "data",
) -> None:
    if value is None:
        return

    if isinstance(value, bool):
        return

    if isinstance(value, int):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceSchemaError(
                f"{path} contains a non-finite float"
            )
        return

    if isinstance(value, str):
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json_value(
                item,
                path=f"{path}[{index}]",
            )
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise EvidenceSchemaError(
                    f"{path} contains a non-string key"
                )

            validate_json_value(
                item,
                path=f"{path}.{key}",
            )
        return

    raise EvidenceSchemaError(
        f"{path} contains unsupported type "
        f"{type(value).__name__}"
    )


def canonical_json(
    value: object,
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class EvidenceHead:
    schema: str
    sequence: int
    record_hash: str
