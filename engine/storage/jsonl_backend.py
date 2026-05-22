import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from engine.storage.base import StorageBackend


class LocalJsonlAppendBackend(StorageBackend):
    def __init__(self, base_dir="data_lake"):
        self.base_dir = os.path.abspath(base_dir)

    def _resolve_path(self, zone, namespace, partition):
        namespace_path = namespace.replace(".", os.sep)
        partition_path = f"partition={partition}"

        return os.path.join(
            self.base_dir,
            zone,
            namespace_path,
            partition_path,
        )

    def _resolve_file(self, zone, namespace, partition):
        target_dir = self._resolve_path(zone, namespace, partition)
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, "data.jsonl")

    def append_record(self, zone, namespace, partition, record):
        file_path = self._resolve_file(zone, namespace, partition)

        record_with_metadata = dict(record)
        record_with_metadata["_lakehouse"] = {
            "zone": zone,
            "namespace": namespace,
            "partition": partition,
            "format": "jsonl",
            "written_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(file_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(record_with_metadata) + "\n")

        return record_with_metadata

    def append_records(self, zone, namespace, partition, records):
        written_records = []

        for record in records:
            written_records.append(
                self.append_record(
                    zone=zone,
                    namespace=namespace,
                    partition=partition,
                    record=record,
                )
            )

        return written_records

    def read_records(self, namespace, partition, version=None, zone="raw"):
        file_path = self._resolve_file(zone, namespace, partition)

        if not os.path.exists(file_path):
            return []

        records = []

        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if line:
                    records.append(json.loads(line))

        return records

    def write_records(self, namespace, partition, version=None, records=None, zone="raw"):
        records = records or []

        file_path = self._resolve_file(zone, namespace, partition)

        with open(file_path, "w", encoding="utf-8") as file:
            for record in records:
                record_with_metadata = dict(record)
                record_with_metadata["_lakehouse"] = {
                    "zone": zone,
                    "namespace": namespace,
                    "partition": partition,
                    "format": "jsonl",
                    "written_at": datetime.now(timezone.utc).isoformat(),
                }

                file.write(json.dumps(record_with_metadata) + "\n")
