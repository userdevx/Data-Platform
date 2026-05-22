# Gold Layer

## Software Specification

The gold layer is the analytics-ready layer in the Data Platform lakehouse architecture.

It stores summarized, aggregated, modeled, and query-optimized records for dashboards, reports, monitoring, exports, and future AI-assisted workflows.

## Purpose

The gold layer provides clean, trusted, analytics-ready data for users, applications, dashboards, reports, and automation.

## Responsibilities

- Create analytics-ready datasets.
- Aggregate events.
- Build summary records.
- Support dashboard metrics.
- Support query results.
- Support reporting workflows.
- Support monitoring views.
- Support export workflows.
- Support future AI analysis.

## Input

The gold layer receives records from:

```text
data_lake/silver/
