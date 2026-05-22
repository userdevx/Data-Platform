# Data Platform Architecture

## Purpose

The Data Platform is a unified data and analytics platform designed to keep the full data lifecycle inside one connected system.

## Core Flow

sources
→ ingestion
→ centralized storage
→ processing
→ query layer
→ dashboards / applications / AI

## Main Layers

1. Data Ingestion
2. Source Normalization
3. Data Quality
4. Storage Abstraction
5. Lakehouse Storage
6. Processing Pipelines
7. Partitioned Querying
8. Desktop User Interface
9. Command-Line Troubleshooting

## Lakehouse Layout

data_lake/raw
data_lake/bronze
data_lake/silver
data_lake/gold

raw = incoming data
bronze = normalized data
silver = cleaned data
gold = analytics-ready data

## Current Storage

JSONL append files are used for streaming-style ingestion.
Parquet files are used for analytics-ready storage.

## Design Direction

The system is local-first, modular, file-based, append-oriented, and designed for future cloud/object storage support.
