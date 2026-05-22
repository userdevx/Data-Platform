# Bronze Layer

## Software Specification

The bronze layer is the normalization layer in the Data Platform lakehouse architecture.

It stores records after raw ingestion data has been converted into the standard Data Platform schema.

## Purpose

The bronze layer standardizes records from different sources into a consistent structure while preserving original source metadata.

## Responsibilities

- Normalize raw records.
- Standardize source categories.
- Standardize sensor and event names.
- Preserve original source details.
- Add source identifiers.
- Add source labels.
- Prepare records for validation.
- Maintain metadata traceability.

## Input

The bronze layer receives records from:

```text
data_lake/raw/
