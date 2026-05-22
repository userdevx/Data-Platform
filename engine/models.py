from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from engine.exceptions import ValidationError


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SensorRecord:
    id: int
    source: str
    category: str
    sensor_type: str
    value: float
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

        if not isinstance(self.sensor_type, str) or not self.sensor_type.strip():
            raise ValidationError("Field 'sensor_type' must be a non-empty string")

        if not isinstance(self.value, (int, float)):
            raise ValidationError("Field 'value' must be a number")

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
    def create(cls, id, source, category, sensor_type, value, unit):
        now = current_timestamp()
        return cls(
            id=id,
            source=source,
            category=category,
            sensor_type=sensor_type,
            value=float(value),
            unit=unit,
            created_at=now,
            updated_at=now,
        )
