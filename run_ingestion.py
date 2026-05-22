from engine.backend import get_backend
from engine.query import QueryService
from engine.input.system import get_all_temperatures
from engine.input.camera import get_camera_record


backend = get_backend()
service = QueryService(backend)


def next_id():
    records = service.get_all_records()

    if not records:
        return 1

    return max(record["id"] for record in records) + 1


def insert_record(record, record_id, label):
    if record is None:
        return record_id

    record["id"] = record_id
    result = service.insert_record(record)

    print({
        "message": f"Inserted {label} record",
        "record": result
    })

    return record_id + 1


def main():
    current_id = next_id()

    temperature_records = get_all_temperatures()

    for record in temperature_records:
        current_id = insert_record(record, current_id, "sensor")

    camera_record = get_camera_record()
    current_id = insert_record(camera_record, current_id, "camera")


if __name__ == "__main__":
    main()
