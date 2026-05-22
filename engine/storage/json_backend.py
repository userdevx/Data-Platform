import json
import os
import shutil

from engine.exceptions import DuplicateRecordError, RecordNotFoundError
from engine.storage.base import StorageBackend


class LocalJsonStorageBackend(StorageBackend):
    def __init__(self, data_file):
        self.data_file = data_file
        self.temp_file = f"{self.data_file}.tmp"
        self.backup_file = f"{self.data_file}.backup"
        self.initialize_storage()

    def initialize_storage(self):
        directory = os.path.dirname(self.data_file)

        if directory:
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(self.data_file):
            self.save_records([])

    def load_records(self):
        self.initialize_storage()

        try:
            with open(self.data_file, "r", encoding="utf-8") as file:
                content = file.read().strip()

                if not content:
                    return []

                return json.loads(content)

        except json.JSONDecodeError:
            if os.path.exists(self.backup_file):
                shutil.copyfile(self.backup_file, self.data_file)
                return self.load_records()

            return []

    def save_records(self, records):
        with open(self.temp_file, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)

        with open(self.temp_file, "r", encoding="utf-8") as file:
            json.load(file)

        if os.path.exists(self.data_file):
            shutil.copyfile(self.data_file, self.backup_file)

        os.replace(self.temp_file, self.data_file)

    # Required by StorageBackend abstraction
    def read_records(self, namespace=None, partition=None, version=None):
        return self.load_records()

    # Required by StorageBackend abstraction
    def write_records(self, namespace=None, partition=None, version=None, records=None):
        self.save_records(records or [])

    def insert_record(self, record):
        records = self.load_records()

        for existing_record in records:
            if existing_record["id"] == record["id"]:
                raise DuplicateRecordError(
                    f"Record with id {record['id']} already exists"
                )

        records.append(record)
        self.save_records(records)
        return record

    def get_all_records(self):
        return self.load_records()

    def get_record_by_id(self, record_id):
        records = self.load_records()

        for record in records:
            if record["id"] == record_id:
                return record

        raise RecordNotFoundError(f"Record with id {record_id} not found")

    def update_record(self, record_id, updated_data):
        records = self.load_records()

        for record in records:
            if record["id"] == record_id:
                record.update(updated_data)
                self.save_records(records)
                return record

        raise RecordNotFoundError(f"Record with id {record_id} not found")

    def delete_record(self, record_id):
        records = self.load_records()
        new_records = [
            record for record in records
            if record["id"] != record_id
        ]

        if len(new_records) == len(records):
            raise RecordNotFoundError(f"Record with id {record_id} not found")

        self.save_records(new_records)
        return {"message": f"Record with id {record_id} deleted"}
