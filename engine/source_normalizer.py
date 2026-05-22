def normalize_source_record(record):
    normalized = dict(record)
    metadata = dict(normalized.get("metadata", {}))

    original_source = normalized.get("source", "unknown_source")
    original_sensor_type = normalized.get("sensor_type", "unknown_sensor")

    normalized["source"] = metadata.get("source_type", "edge_device")
    normalized["source_id"] = metadata.get(
        "source_id",
        f"src_{original_source}"
    )
    normalized["source_label"] = metadata.get(
        "source_label",
        original_source.replace("_", " ").title()
    )

    metadata["original_source"] = original_source
    metadata["original_sensor_type"] = original_sensor_type
    metadata["hardware_platform"] = metadata.get(
        "hardware_platform",
        original_source
    )
    metadata["sensor_model"] = metadata.get(
        "sensor_model",
        original_sensor_type
    )

    if original_sensor_type == "hc_sr501_pir":
        normalized["sensor_type"] = "pir_motion_sensor"

    normalized["metadata"] = metadata

    return normalized
