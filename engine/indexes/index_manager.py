class IndexManager:
    def __init__(self):
        self.indexes = {}

    def build_indexes(self, records):
        self.indexes = {}

        for record in records:
            self.add_record(record)

    def add_record(self, record):
        for field_name, field_value in record.items():
            self._add_to_index(field_name, field_value, record)

    def _add_to_index(self, field_name, field_value, record):
        if field_value is None:
            return

        if isinstance(field_value, (dict, list)):
            return

        if field_name not in self.indexes:
            self.indexes[field_name] = {}

        if field_value not in self.indexes[field_name]:
            self.indexes[field_name][field_value] = []

        self.indexes[field_name][field_value].append(record)

    def get_by_index(self, field_name, field_value):
        return self.indexes.get(field_name, {}).get(field_value, [])

    def has_index(self, field_name):
        return field_name in self.indexes
