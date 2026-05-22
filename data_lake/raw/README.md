# Raw Layer

## Software Specification

The raw layer is the first storage layer in the Data Platform lakehouse architecture.

It stores incoming records exactly as they enter the system before normalization, validation, cleaning, aggregation, or analytics processing.

## Purpose

The raw layer preserves original incoming data for traceability, replay, recovery, and audit workflows.

## Responsibilities

- Store incoming ingestion records.
- Preserve original source data.
- Support append-only ingestion.
- Maintain source traceability.
- Provide replayable records for future processing.
- Protect original records from manual modification.

## Input

Records may enter from operating system sources, connected devices, files, logs, applications, sensors, cameras, streams, future APIs, and future cloud services.

## Output

The raw layer outputs records to the bronze layer.

## Storage Format

Current format:

- JSONL

Future supported formats:

- Parquet
- object storage files

## Folder Pattern

```text
data_lake/raw/<namespace>/partition=YYYY-MM-DD/data.jsonl
