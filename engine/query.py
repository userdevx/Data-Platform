from engine.validation import validate_record
from engine.indexes.index_manager import IndexManager
from engine.query_performance import estimate_query_performance


class QueryService:
    def __init__(self, backend):
        self.backend = backend
        self.index_manager = IndexManager()
        self.rebuild_indexes()

    def rebuild_indexes(self):
        records = self.backend.get_all_records()
        self.index_manager.build_indexes(records)

    def get_indexed_fields(self):
        return list(self.index_manager.indexes.keys())

    def estimate_where_performance(self, field_name, operator, limit=None):
        records = self.backend.get_all_records()

        return estimate_query_performance(
            total_records=len(records),
            field_name=field_name,
            operator=operator,
            limit=limit,
            indexed_fields=self.get_indexed_fields(),
        )

    def apply_limit(self, records, limit=None):
        if limit is None:
            return records

        return records[:limit]

    def insert_record(self, record):
        validate_record(record)
        result = self.backend.insert_record(record)
        self.rebuild_indexes()
        return result

    def get_all_records(self, limit=None):
        records = self.backend.get_all_records()
        return self.apply_limit(records, limit)

    def get_record_by_id(self, record_id):
        indexed_results = self.index_manager.get_by_index("id", record_id)

        if indexed_results:
            return indexed_results[0]

        return self.backend.get_record_by_id(record_id)

    def update_record(self, record_id, updated_data):
        current_record = self.get_record_by_id(record_id)
        merged_record = {**current_record, **updated_data}
        validate_record(merged_record)

        result = self.backend.update_record(record_id, updated_data)
        self.rebuild_indexes()
        return result

    def delete_record(self, record_id):
        self.backend.delete_record(record_id)
        self.rebuild_indexes()
        return {"message": f"Record with id {record_id} deleted"}

    def where(self, field_name, operator, field_value, limit=None):
        records = self.backend.get_all_records()
        results = []

        for record in records:
            record_value = record.get(field_name)

            if record_value is None:
                continue

            if operator == "=":
                if str(record_value) == str(field_value):
                    results.append(record)

            elif operator == "!=":
                if str(record_value) != str(field_value):
                    results.append(record)

            elif operator in [">", ">=", "<", "<="]:
                try:
                    record_number = float(record_value)
                    query_number = float(field_value)
                except ValueError:
                    continue

                if operator == ">" and record_number > query_number:
                    results.append(record)

                elif operator == ">=" and record_number >= query_number:
                    results.append(record)

                elif operator == "<" and record_number < query_number:
                    results.append(record)

                elif operator == "<=" and record_number <= query_number:
                    results.append(record)

            else:
                raise ValueError(f"Unsupported operator: {operator}")

        return self.apply_limit(results, limit)

    def filter_by_field(self, field_name, field_value, limit=None):
        return self.where(field_name, "=", field_value, limit)

    def filter_value_greater_than(self, value, limit=None):
        return self.where("value", ">", value, limit)

    def filter_value_less_than(self, value, limit=None):
        return self.where("value", "<", value, limit)

    def sort_by_field(self, field_name, reverse=False, limit=None):
        records = self.backend.get_all_records()

        sorted_records = sorted(
            records,
            key=lambda record: record.get(field_name, ""),
            reverse=reverse
        )

        return self.apply_limit(sorted_records, limit)
