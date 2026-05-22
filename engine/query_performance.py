def estimate_query_performance(
    total_records,
    field_name,
    operator,
    limit=None,
    indexed_fields=None,
):
    indexed_fields = indexed_fields or []

    uses_index = field_name in indexed_fields
    estimated_scan_count = total_records

    if limit is not None:
        estimated_scan_count = min(total_records, limit)

    if uses_index:
        performance_level = "low"
    elif estimated_scan_count <= 100:
        performance_level = "medium"
    else:
        performance_level = "high"

    warning = None

    if performance_level == "high":
        warning = (
            "High query workload detected. "
            "Consider adding indexes or reducing the limit."
        )

    return {
        "field_name": field_name,
        "operator": operator,
        "total_records": total_records,
        "limit": limit,
        "uses_index": uses_index,
        "estimated_scan_count": estimated_scan_count,
        "performance_level": performance_level,
        "warning": warning,
    }
