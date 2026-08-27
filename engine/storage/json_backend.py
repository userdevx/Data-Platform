import json
import os
import shutil
from contextlib import contextmanager
from threading import RLock

import fcntl

from engine.exceptions import (
    DuplicateRecordError,
    RecordNotFoundError,
)
from engine.storage.base import (
    StorageBackend,
)


_MISSING_RECORD_ID = object()


def _record_id(record):
    """
    Return a record's canonical top-level id.

    Historical Data Engine records may use older schemas
    without a top-level id. Those records remain readable
    and must not prevent newer canonical records from being
    inserted, queried, updated, or deleted.
    """

    if not isinstance(
        record,
        dict,
    ):
        return _MISSING_RECORD_ID

    return record.get(
        "id",
        _MISSING_RECORD_ID,
    )


class LocalJsonStorageBackend(
    StorageBackend
):
    def __init__(
        self,
        data_file,
    ):
        self.data_file = data_file
        self.temp_file = (
            f"{self.data_file}.tmp"
        )
        self.backup_file = (
            f"{self.data_file}.backup"
        )
        self.lock_file = (
            f"{self.data_file}.lock"
        )

        self._process_lock = RLock()

        directory = os.path.dirname(
            self.data_file
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

        self.initialize_storage()

    @contextmanager
    def _exclusive_lock(
        self,
    ):
        """
        Serialize storage operations inside this process
        and across Linux processes that use this backend.
        """

        with self._process_lock:
            with open(
                self.lock_file,
                "a+",
                encoding="utf-8",
            ) as lock_handle:
                fcntl.flock(
                    lock_handle.fileno(),
                    fcntl.LOCK_EX,
                )

                try:
                    yield
                finally:
                    fcntl.flock(
                        lock_handle.fileno(),
                        fcntl.LOCK_UN,
                    )

    def initialize_storage(
        self,
    ):
        with self._exclusive_lock():
            if not os.path.exists(
                self.data_file
            ):
                self._save_records_unlocked(
                    []
                )

    def _load_records_unlocked(
        self,
    ):
        if not os.path.exists(
            self.data_file
        ):
            self._save_records_unlocked(
                []
            )

        try:
            with open(
                self.data_file,
                "r",
                encoding="utf-8",
            ) as file:
                content = (
                    file.read().strip()
                )

                if not content:
                    return []

                return json.loads(
                    content
                )

        except json.JSONDecodeError:
            if os.path.exists(
                self.backup_file
            ):
                shutil.copyfile(
                    self.backup_file,
                    self.data_file,
                )

                with open(
                    self.data_file,
                    "r",
                    encoding="utf-8",
                ) as file:
                    content = (
                        file.read().strip()
                    )

                    if not content:
                        return []

                    return json.loads(
                        content
                    )

            return []

    def load_records(
        self,
    ):
        with self._exclusive_lock():
            return self._load_records_unlocked()

    def _save_records_unlocked(
        self,
        records,
    ):
        with open(
            self.temp_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                records,
                file,
                indent=2,
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

        with open(
            self.temp_file,
            "r",
            encoding="utf-8",
        ) as file:
            json.load(
                file
            )

        if os.path.exists(
            self.data_file
        ):
            shutil.copyfile(
                self.data_file,
                self.backup_file,
            )

        os.replace(
            self.temp_file,
            self.data_file,
        )

    def save_records(
        self,
        records,
    ):
        with self._exclusive_lock():
            self._save_records_unlocked(
                records
            )

    # Required by StorageBackend abstraction
    def read_records(
        self,
        namespace=None,
        partition=None,
        version=None,
    ):
        return self.load_records()

    # Required by StorageBackend abstraction
    def write_records(
        self,
        namespace=None,
        partition=None,
        version=None,
        records=None,
    ):
        self.save_records(
            records or []
        )

    def insert_record(
        self,
        record,
    ):
        if not isinstance(
            record,
            dict,
        ):
            raise TypeError(
                "record must be a dictionary"
            )

        new_record_id = _record_id(
            record
        )

        if (
            new_record_id
            is _MISSING_RECORD_ID
        ):
            raise ValueError(
                "record must contain a "
                "top-level 'id'"
            )

        with self._exclusive_lock():
            records = (
                self._load_records_unlocked()
            )

            for existing_record in records:
                existing_record_id = (
                    _record_id(
                        existing_record
                    )
                )

                if (
                    existing_record_id
                    is _MISSING_RECORD_ID
                ):
                    continue

                if (
                    existing_record_id
                    == new_record_id
                ):
                    raise DuplicateRecordError(
                        "Record with id "
                        f"{new_record_id} "
                        "already exists"
                    )

            records.append(
                record
            )

            self._save_records_unlocked(
                records
            )

        return record

    def get_all_records(
        self,
    ):
        return self.load_records()

    def get_record_by_id(
        self,
        record_id,
    ):
        with self._exclusive_lock():
            records = (
                self._load_records_unlocked()
            )

            for record in records:
                existing_record_id = (
                    _record_id(
                        record
                    )
                )

                if (
                    existing_record_id
                    is _MISSING_RECORD_ID
                ):
                    continue

                if (
                    existing_record_id
                    == record_id
                ):
                    return record

        raise RecordNotFoundError(
            f"Record with id "
            f"{record_id} not found"
        )

    def update_record(
        self,
        record_id,
        updated_data,
    ):
        with self._exclusive_lock():
            records = (
                self._load_records_unlocked()
            )

            for record in records:
                existing_record_id = (
                    _record_id(
                        record
                    )
                )

                if (
                    existing_record_id
                    is _MISSING_RECORD_ID
                ):
                    continue

                if (
                    existing_record_id
                    == record_id
                ):
                    record.update(
                        updated_data
                    )

                    self._save_records_unlocked(
                        records
                    )

                    return record

        raise RecordNotFoundError(
            f"Record with id "
            f"{record_id} not found"
        )

    def delete_record(
        self,
        record_id,
    ):
        with self._exclusive_lock():
            records = (
                self._load_records_unlocked()
            )

            new_records = []
            found = False

            for record in records:
                existing_record_id = (
                    _record_id(
                        record
                    )
                )

                if (
                    existing_record_id
                    is not _MISSING_RECORD_ID
                    and existing_record_id
                    == record_id
                ):
                    found = True
                    continue

                new_records.append(
                    record
                )

            if not found:
                raise RecordNotFoundError(
                    f"Record with id "
                    f"{record_id} not found"
                )

            self._save_records_unlocked(
                new_records
            )

        return {
            "message": (
                f"Record with id "
                f"{record_id} deleted"
            )
        }
