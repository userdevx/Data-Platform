from engine.backend import get_backend
from engine.exceptions import EngineError
from engine.logger import log_error, log_info
from engine.models import SensorRecord
from engine.output import format_response
from engine.query import QueryService


def prompt_for_int(message):
    while True:
        user_input = input(message).strip()

        try:
            return int(user_input)
        except ValueError:
            print("Please enter a whole number only.")


def prompt_for_float(message):
    while True:
        user_input = input(message).strip()

        try:
            return float(user_input)
        except ValueError:
            print("Please enter a number only.")


def prompt_for_page():
    user_input = input("Enter page (blank for 1): ").strip()

    if not user_input:
        return 1

    try:
        page = int(user_input)
        return page if page > 0 else 1
    except ValueError:
        print("Invalid page. Using page 1.")
        return 1


def prompt_for_limit():
    user_input = input("Enter limit (blank for 10): ").strip()

    if not user_input:
        return 10

    try:
        limit = int(user_input)
        return limit if limit > 0 else 10
    except ValueError:
        print("Invalid limit. Using limit 10.")
        return 10


def show_records(records, event_name):
    page = prompt_for_page()
    limit = prompt_for_limit()

    log_info(
        event_name,
        f"records={len(records)} page={page} limit={limit}"
    )

    print(format_response(records, page=page, limit=limit))


def main():
    backend = get_backend()
    service = QueryService(backend)

    log_info("engine_start", "Data engine CLI started")

    while True:
        command = input("engine > ").strip().lower()

        try:
            log_info("command_received", f"command={command}")

            if command == "exit":
                log_info("engine_exit", "Data engine CLI exited")
                print("Exiting engine")
                break

            elif command == "insert":
                sensor_record = SensorRecord.create(
                    id=prompt_for_int("Enter id: "),
                    source=input("Enter source: ").strip(),
                    category=input("Enter category: ").strip(),
                    sensor_type=input("Enter sensor type: ").strip(),
                    value=prompt_for_float("Enter value: "),
                    unit=input("Enter unit: ").strip(),
                )

                result = service.insert_record(sensor_record.to_dict())

                log_info(
                    "record_inserted",
                    f"id={result.get('id')}"
                )

                print({
                    "message": "Record inserted",
                    "record": result
                })

            elif command == "read":
                records = service.get_all_records()
                show_records(records, "read_executed")

            elif command == "get":
                record_id = prompt_for_int("Enter id: ")
                result = service.get_record_by_id(record_id)

                log_info(
                    "get_executed",
                    f"id={record_id}"
                )

                print(result)

            elif command == "delete":
                record_id = prompt_for_int("Enter id: ")
                result = service.delete_record(record_id)

                log_info(
                    "record_deleted",
                    f"id={record_id}"
                )

                print(result)

            elif command == "filter":
                field_name = input("Enter field name: ").strip()
                field_value = input("Enter field value: ").strip()

                records = service.filter_by_field(
                    field_name,
                    field_value
                )

                log_info(
                    "filter_executed",
                    (
                        f"field={field_name} "
                        f"value={field_value} "
                        f"results={len(records)}"
                    )
                )

                show_records(records, "filter_output")

            elif command == "where":
                field_name = input("Enter field name: ").strip()

                operator = input(
                    "Enter operator (=, !=, >, >=, <, <=): "
                ).strip()

                field_value = input("Enter value: ").strip()

                performance = service.estimate_where_performance(
                    field_name,
                    operator,
                )

                print(
                    f"performance_level={performance['performance_level']} | "
                    f"uses_index={performance['uses_index']} | "
                    f"estimated_scan_count={performance['estimated_scan_count']} | "
                    f"warning={performance['warning']}"
                )

                records = service.where(
                    field_name,
                    operator,
                    field_value,
                )

                log_info(
                    "where_executed",
                    (
                        f"field={field_name} "
                        f"operator={operator} "
                        f"value={field_value} "
                        f"results={len(records)} "
                        f"performance_level={performance['performance_level']} "
                        f"uses_index={performance['uses_index']}"
                    )
                )

                show_records(records, "where_output")

            elif command == "greater":
                value = prompt_for_float("Enter value: ")

                records = service.filter_value_greater_than(value)

                log_info(
                    "greater_executed",
                    f"value={value} results={len(records)}"
                )

                show_records(records, "greater_output")

            elif command == "less":
                value = prompt_for_float("Enter value: ")

                records = service.filter_value_less_than(value)

                log_info(
                    "less_executed",
                    f"value={value} results={len(records)}"
                )

                show_records(records, "less_output")

            elif command == "sort":
                field_name = input("Enter field name: ").strip()

                records = service.sort_by_field(field_name)

                log_info(
                    "sort_executed",
                    f"field={field_name} results={len(records)}"
                )

                show_records(records, "sort_output")

            else:
                log_error(
                    "unknown_command",
                    f"command={command}"
                )

                print(
                    "Unknown command. Use: insert, read, get, "
                    "delete, filter, where, greater, less, sort, exit"
                )

        except EngineError as error:
            log_error("engine_error", str(error))
            print({"error": str(error)})

        except ValueError as error:
            log_error("value_error", str(error))
            print({"error": str(error)})


if __name__ == "__main__":
    main()
