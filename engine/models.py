from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from engine.exceptions import ValidationError


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DataRecord:
    id: int
    source: str
    category: str
    data_type: str
    value: Any
    unit: str
    created_at: str
    updated_at: str

    def validate(self):
        if not isinstance(self.id, int):
            raise ValidationError("Field 'id' must be an integer")

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValidationError("Field 'source' must be a non-empty string")

        if not isinstance(self.category, str) or not self.category.strip():
            raise ValidationError("Field 'category' must be a non-empty string")

        if not isinstance(self.data_type, str) or not self.data_type.strip():
            raise ValidationError("Field 'data_type' must be a non-empty string")

        if self.value is None:
            raise ValidationError("Field 'value' cannot be empty")

        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValidationError("Field 'unit' must be a non-empty string")

        if not isinstance(self.created_at, str) or not self.created_at.strip():
            raise ValidationError("Field 'created_at' must be a non-empty string")

        if not isinstance(self.updated_at, str) or not self.updated_at.strip():
            raise ValidationError("Field 'updated_at' must be a non-empty string")

    def to_dict(self):
        self.validate()
        return asdict(self)

    @classmethod
    def create(cls, id, source, category, data_type, value, unit):
        now = current_timestamp()

        return cls(
            id=id,
            source=source,
            category=category,
            data_type=data_type,
            value=value,
            unit=unit,
            created_at=now,
            updated_at=now,
        )