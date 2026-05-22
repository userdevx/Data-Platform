import os
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq

from engine.storage.base import StorageBackend


class LocalParquetStorageBackend(StorageBackend):
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

        return os.path.join(target_dir, "data.parquet")

    def write_records(self, namespace, partition, version=None, records=None, zone="silver"):
        records = records or []

        records_to_write = []

        for record in records:
            clean_record = dict(record)
            clean_record["_lakehouse_zone"] = zone
            clean_record["_lakehouse_namespace"] = namespace
            clean_record["_lakehouse_partition"] = partition
            clean_record["_lakehouse_format"] = "parquet"
            clean_record["_lakehouse_written_at"] = datetime.now(timezone.utc).isoformat()

            records_to_write.append(clean_record)

        file_path = self._resolve_file(zone, namespace, partition)

        table = pa.Table.from_pylist(records_to_write)
        pq.write_table(table, file_path)

        return file_path

    def read_records(self, namespace, partition, version=None, zone="silver"):
        file_path = self._resolve_file(zone, namespace, partition)

        if not os.path.exists(file_path):
            return []

        table = pq.read_table(file_path)
        return table.to_pylist()
