from datetime import datetime, timezone

from engine.storage.jsonl_backend import LocalJsonlAppendBackend


lakehouse_backend = LocalJsonlAppendBackend()


def write_record_to_lakehouse(record):
    timestamp = datetime.now(timezone.utc)

    partition = timestamp.strftime("%Y-%m-%d")

    category = record.get("category", "unknown")
    namespace = f"{category}_events"

    return lakehouse_backend.append_record(
        zone="raw",
        namespace=namespace,
        partition=partition,
        record=record,
    )
