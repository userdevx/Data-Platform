from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

from engine.data_engine.record_writer import DataEngineRecordWriter

PREFIX = "DATAWORC_BUILD_EVENT:"
_sequence = 0


def emit_event(kind: str, **details: object) -> None:
    """Persist and publish an actual Builder operation."""
    global _sequence

    session = os.environ.get("DATAWORC_BUILD_SESSION_ID", "")
    if not session:
        return

    if not re.fullmatch(r"[a-zA-Z0-9-]{1,128}", session):
        raise ValueError("Invalid Builder session identifier")

    if not re.fullmatch(r"[a-z_]{3,48}", kind):
        raise ValueError("Invalid Builder event kind")

    _sequence += 1

    event = {
        "session_id": session,
        "sequence": _sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "details": details,
    }

    # Data Engine persistence precedes event transmission.
    DataEngineRecordWriter().write(
        source="application_generation",
        category="application_generation",
        data_type="build_event",
        value=event,
        unit="record",
    )

    sys.stderr.write(
        PREFIX + json.dumps(event, separators=(",", ":")) + "\n"
    )
    sys.stderr.flush()
