import os
from typing import Optional

from engine.storage.base import (
    LocalParquetStorageBackendPlaceholder,
    StorageBackend,
)
from engine.storage.local_json import LocalJsonStorageBackend
from engine.storage.jsonl_backend import LocalJsonlAppendBackend
from engine.storage.parquet_backend import LocalParquetStorageBackend

class StorageBackendLoader:
    _instance: Optional[StorageBackend] = None

    @classmethod
    def configure(cls, backend_type, base_dir="./data_warehouse"):
        if backend_type == "local_json":
            cls._instance = LocalJsonStorageBackend(base_dir=base_dir)

        elif backend_type == "local_jsonl":
            cls._instance = LocalJsonlAppendBackend(base_dir=base_dir)

        elif backend_type == "parquet_placeholder":
            cls._instance = LocalParquetStorageBackendPlaceholder()

        elif backend_type == "local_parquet":
             cls._instance = LocalParquetStorageBackend(base_dir=base_dir)


        else:
            raise ValueError(f"Unsupported storage backend type: {backend_type}")

        return cls._instance

    @classmethod
    def get_backend(cls):
        if cls._instance is None:
            backend_type = os.getenv("DATA_ENGINE_BACKEND", "local_json")
            base_dir = os.getenv("DATA_ENGINE_BASE_DIR", "./data_warehouse")
            cls.configure(backend_type, base_dir)

        return cls._instance
