import json
import os


def build_partition_path(
    zone="raw",
    namespace="motion_events",
    partition=None,
    base_dir="data_lake",
):
    if partition is None:
        raise ValueError("partition is required")

    return os.path.join(
        base_dir,
        zone,
        namespace,
        f"partition={partition}",
        "data.jsonl",
    )


def read_partition(
    zone="raw",
    namespace="motion_events",
    partition=None,
    base_dir="data_lake",
):
    file_path = build_partition_path(
        zone=zone,
        namespace=namespace,
        partition=partition,
        base_dir=base_dir,
    )

    if not os.path.exists(file_path):
        return []

    records = []

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if line:
                records.append(json.loads(line))

    return records


def filter_records(records, source=None, data_type=None, category=None):
    results = []

    for record in records:
        if source is not None and record.get("source") != source:
            continue

        if data_type is not None and record.get("data_type") != data_type:
            continue

        if category is not None and record.get("category") != category:
            continue

        results.append(record)

    return results


def query_lakehouse_partition(
    partition,
    zone="raw",
    namespace="motion_events",
    source=None,
    data_type=None,
    category=None,
    base_dir="data_lake",
):
    records = read_partition(
        zone=zone,
        namespace=namespace,
        partition=partition,
        base_dir=base_dir,
    )

    filtered_records = filter_records(
        records,
        source=source,
        data_type=data_type,
        category=category,
    )

    return {
        "zone": zone,
        "namespace": namespace,
        "partition": partition,
        "records_scanned": len(records),
        "records_returned": len(filtered_records),
        "data": filtered_records,
    }
