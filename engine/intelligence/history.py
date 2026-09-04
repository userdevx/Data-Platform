from __future__ import annotations

import json
from pathlib import Path

from engine.intelligence.models import IntelligenceRequest, IntelligenceResponse


class IntelligenceHistoryWriter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.history_dir = self.root / "data" / "intelligence"
        self.history_file = self.history_dir / "history.jsonl"
        self.error_file = self.history_dir / "errors.jsonl"

    def write(
        self,
        request: IntelligenceRequest,
        response: IntelligenceResponse,
    ) -> Path:
        self.history_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "source": "intelligence",
            "category": "intelligence_history",
            "data_type": "intelligence_response",
            "value": {
                "request": request.to_dict(),
                "response": response.to_dict(),
            },
            "unit": "record",
            "timestamp": response.created_at,
        }

        if response.status in {"error", "rejected", "not_found"}:
            path = self.error_file
        else:
            path = self.history_file

        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

        return path
