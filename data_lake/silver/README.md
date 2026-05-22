# Silver Layer

## Software Specification

The silver layer is the validated and cleaned data layer in the Data Platform lakehouse architecture.

It stores records that passed validation, normalization, and data quality checks before analytics processing.

## Purpose

The silver layer prevents invalid, malformed, duplicated, or corrupted data from reaching dashboards, analytics systems, exports, and future AI workflows.

## Responsibilities

- Validate required fields.
- Validate source categories.
- Validate timestamp format.
- Validate sensor values.
- Detect duplicate identifiers.
- Detect missing file references.
- Remove malformed records.
- Prepare trusted analytics-ready records.
- Support downstream querying.

## Input

The silver layer receives records from:

```text
data_lake/bronze/
