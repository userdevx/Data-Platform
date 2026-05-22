import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from engine.storage.base import StorageBackend


class LocalJsonStorageBackend(StorageBackend):
    def __init__(self, base_dir: str = "./data_warehouse"):
        self.base_dir = os.path.abspath(base_dir)

    def _resolve_path(self, namespace: str, partition: str) -> str:
        namespace_path = namespace.replace(".", os.sep)
        partition_path = f"partition={partition}"

        return os.path.join(
            self.base_dir,
            namespace_path,
            partition_path,
        )

    def read_records(
        self,
        namespace: str,
        partition: str,
        version: str,
    ) -> List[Dict[str, Any]]:
        target_dir = self._resolve_path(namespace, partition)
        file_path = os.path.join(target_dir, f"data_v{version}.json")

        if not os.path.exists(file_path):
            return []

        with open(file_path, "r", encoding="utf-8") as file:
            envelope = json.load(file)
            return envelope.get("records", [])

    def write_records(
        self,
        namespace: str,
        partition: str,
        version: str,
        records: List[Dict[str, Any]],
    ) -> None:
        target_dir = self._resolve_path(namespace, partition)
        os.makedirs(target_dir, exist_ok=True)

        file_path = os.path.join(target_dir, f"data_v{version}.json")

        envelope = {
            "metadata": {
                "schema_version": version,
                "format": "JSON",
                "namespace": namespace,
                "partition": partition,
                "record_count": len(records),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "records": records,
        }

        temp_file = f"{file_path}.tmp"

        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(envelope, file, indent=2)

        with open(temp_file, "r", encoding="utf-8") as file:
            json.load(file)

        os.replace(temp_file, file_path)
