from datetime import datetime, timezone

from engine.data_quality import validate_data_quality
from engine.lakehouse_writer import write_record_to_lakehouse
from engine.source_normalizer import normalize_source_record


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def process_data(record):
    normalized_record = normalize_source_record(record)
    quality_result = validate_data_quality(normalized_record)

    if not quality_result["valid"]:
        return {
            "status": "rejected",
            "processed_at": current_timestamp(),
            "errors": quality_result["errors"],
            "record": normalized_record,
        }

    lakehouse_record = write_record_to_lakehouse(normalized_record)

    return {
        "status": "processed",
        "processed_at": current_timestamp(),
        "record": lakehouse_record,
    }
