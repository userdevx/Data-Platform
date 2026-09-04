import os

from engine.source_normalizer import normalize_source_record
from engine.storage.jsonl_backend import LocalJsonlAppendBackend


lakehouse = LocalJsonlAppendBackend(base_dir="data_lake")


def get_partitions(zone, namespace):
    base_path = os.path.join("data_lake", zone, namespace)

    if not os.path.exists(base_path):
        return []

    return [
        name.replace("partition=", "")
        for name in os.listdir(base_path)
        if name.startswith("partition=")
    ]


def raw_to_bronze(namespace="motion_events"):
    partitions = get_partitions("raw", namespace)
    total_written = 0

    for partition in partitions:
        raw_records = lakehouse.read_records(
            zone="raw",
            namespace=namespace,
            partition=partition,
        )

        bronze_records = [
            normalize_source_record(record)
            for record in raw_records
        ]

        lakehouse.write_records(
            zone="bronze",
            namespace=namespace,
            partition=partition,
            records=bronze_records,
        )

        total_written += len(bronze_records)

    return {
        "layer": "bronze",
        "namespace": namespace,
        "records_written": total_written,
    }


def bronze_to_silver(namespace="motion_events"):
    partitions = get_partitions("bronze", namespace)
    total_written = 0

    for partition in partitions:
        bronze_records = lakehouse.read_records(
            zone="bronze",
            namespace=namespace,
            partition=partition,
        )

        silver_records = []

        for record in bronze_records:
            if record.get("category") != "motion":
                continue

            if record.get("value") not in [True, False, 1, 0]:
                continue

            silver_records.append(record)

        lakehouse.write_records(
            zone="silver",
            namespace=namespace,
            partition=partition,
            records=silver_records,
        )

        total_written += len(silver_records)

    return {
        "layer": "silver",
        "namespace": namespace,
        "records_written": total_written,
    }


def silver_to_gold(namespace="motion_events"):
    partitions = get_partitions("silver", namespace)
    total_written = 0

    for partition in partitions:
        silver_records = lakehouse.read_records(
            zone="silver",
            namespace=namespace,
            partition=partition,
        )

        motion_true_count = 0
        motion_false_count = 0

        for record in silver_records:
            value = record.get("value")

            if value in [True, 1]:
                motion_true_count += 1
            elif value in [False, 0]:
                motion_false_count += 1

        gold_record = {
            "category": "analytics",
            "data_type": "motion_summary",
            "partition": partition,
            "motion_true_count": motion_true_count,
            "motion_false_count": motion_false_count,
            "total_records": len(silver_records),
        }

        lakehouse.write_records(
            zone="gold",
            namespace="motion_summary",
            partition=partition,
            records=[gold_record],
        )

        total_written += 1

    return {
        "layer": "gold",
        "namespace": "motion_summary",
        "records_written": total_written,
    }


def run_lakehouse_pipeline():
    bronze_result = raw_to_bronze()
    silver_result = bronze_to_silver()
    gold_result = silver_to_gold()

    return {
        "status": "success",
        "bronze": bronze_result,
        "silver": silver_result,
        "gold": gold_result,
    }
