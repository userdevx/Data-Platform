def paginate_records(records, page=1, limit=10):
    total_count = len(records)

    if page < 1:
        page = 1

    if limit < 1:
        limit = 10

    start = (page - 1) * limit
    end = start + limit

    data = records[start:end]
    count = len(data)

    next_page = page + 1 if end < total_count else None
    previous_page = page - 1 if page > 1 else None

    return {
        "meta": {
            "count": count,
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "next_page": next_page,
            "previous_page": previous_page,
        },
        "data": data,
    }


def get_record_data_type(record):
    return record.get(
        "data_type",
        "",
    )


def format_table(records):
    if not records:
        return "No records found."

    columns = [
        "id",
        "category",
        "data_type",
        "value",
        "unit",
        "created_at",
    ]

    rows = []

    for record in records:
        rows.append([
            str(record.get("id", "")),
            str(record.get("category", "")),
            str(get_record_data_type(record)),
            str(record.get("value", "")),
            str(record.get("unit", "")),
            str(record.get("created_at", "")),
        ])

    widths = []

    for index, column in enumerate(columns):
        max_width = len(column)

        for row in rows:
            max_width = max(max_width, len(row[index]))

        widths.append(max_width)

    header = " | ".join(
        column.ljust(widths[index])
        for index, column in enumerate(columns)
    )

    separator = "-+-".join("-" * width for width in widths)

    body = "\n".join(
        " | ".join(
            row[index].ljust(widths[index])
            for index in range(len(columns))
        )
        for row in rows
    )

    return f"{header}\n{separator}\n{body}"


def format_response(records, page=1, limit=10):
    response = paginate_records(records, page, limit)

    meta = response["meta"]
    data = response["data"]

    meta_text = (
        f"count={meta['count']} | "
        f"total_count={meta['total_count']} | "
        f"page={meta['page']} | "
        f"limit={meta['limit']} | "
        f"next_page={meta['next_page']} | "
        f"previous_page={meta['previous_page']}"
    )

    return f"{meta_text}\n\n{format_table(data)}"