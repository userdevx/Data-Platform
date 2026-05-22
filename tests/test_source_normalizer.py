from engine.source_normalizer import normalize_source_record


def test_source_normalizer_generalizes_source():
    record = {
        "source": "arduino_uno_r4_wifi",
        "category": "motion",
        "sensor_type": "hc_sr501_pir",
        "value": True,
        "unit": "boolean",
    }

    normalized = normalize_source_record(record)

    assert normalized["source"] == "edge_device"
    assert normalized["source_id"] == "src_arduino_uno_r4_wifi"
    assert normalized["source_label"] == "Arduino Uno R4 Wifi"
    assert normalized["sensor_type"] == "pir_motion_sensor"

    assert normalized["metadata"]["original_source"] == "arduino_uno_r4_wifi"
    assert normalized["metadata"]["original_sensor_type"] == "hc_sr501_pir"
    assert normalized["metadata"]["hardware_platform"] == "arduino_uno_r4_wifi"
    assert normalized["metadata"]["sensor_model"] == "hc_sr501_pir"


def test_source_normalizer_accepts_custom_metadata():
    record = {
        "source": "device_001",
        "category": "motion",
        "sensor_type": "custom_sensor",
        "value": False,
        "unit": "boolean",
        "metadata": {
            "source_type": "sensor_node",
            "source_id": "src_sensor_node_001",
            "source_label": "Front Door Sensor Node",
            "hardware_platform": "custom_board",
            "sensor_model": "custom_pir",
        },
    }

    normalized = normalize_source_record(record)

    assert normalized["source"] == "sensor_node"
    assert normalized["source_id"] == "src_sensor_node_001"
    assert normalized["source_label"] == "Front Door Sensor Node"
    assert normalized["metadata"]["hardware_platform"] == "custom_board"
    assert normalized["metadata"]["sensor_model"] == "custom_pir"
