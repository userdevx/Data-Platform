from abc import ABC, abstractmethod
from typing import Any, Dict, List


class StorageBackend(ABC):
    @abstractmethod
    def read_records(
        self,
        namespace: str,
        partition: str,
        version: str,
    ) -> List[Dict[str, Any]]:
        """Read records from a namespace partition."""
        pass

    @abstractmethod
    def write_records(
        self,
        namespace: str,
        partition: str,
        version: str,
        records: List[Dict[str, Any]],
    ) -> None:
        """Write records to a namespace partition."""
        pass


class LocalParquetStorageBackendPlaceholder(StorageBackend):
    def read_records(
        self,
        namespace: str,
        partition: str,
        version: str,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "Parquet backend is planned. Swap configuration to activate."
        )

    def write_records(
        self,
        namespace: str,
        partition: str,
        version: str,
        records: List[Dict[str, Any]],
    ) -> None:
        raise NotImplementedError(
            "Parquet backend is planned. Swap configuration to activate."
        )
