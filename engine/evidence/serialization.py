from __future__ import annotations

import dataclasses
import types
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from uuid import UUID

from engine.evidence.models import (
    Analysis,
    ApplicationRecord,
    ApplicationRequest,
    BuildRecord,
    CodeChange,
    EngineeringCheckpoint,
    EngineeringPlan,
    MaintenanceEvent,
    NormalizedInformation,
    ProductRequirement,
    RawInformation,
    ReleaseRecord,
    RuntimeMetric,
    TestRecord,
    UserRequirement,
    ValidatedTrend,
)


ENTITY_TYPE_BY_CLASS = {
    RawInformation: "raw_information",
    NormalizedInformation: "normalized_information",
    Analysis: "analysis",
    ValidatedTrend: "validated_trend",
    ProductRequirement: "product_requirement",
    ApplicationRequest: "application_request",
    UserRequirement: "user_requirement",
    ApplicationRecord: "application",
    EngineeringPlan: "engineering_plan",
    EngineeringCheckpoint: "engineering_checkpoint",
    CodeChange: "code_change",
    BuildRecord: "build",
    TestRecord: "test",
    ReleaseRecord: "release",
    RuntimeMetric: "runtime_metric",
    MaintenanceEvent: "maintenance_event",
}


ENTITY_CLASS_BY_TYPE = {
    entity_type: entity_class
    for entity_class, entity_type
    in ENTITY_TYPE_BY_CLASS.items()
}


DEFAULT_ENTITY_SOURCE = "structured_knowledge"


ENTITY_SOURCE_BY_CLASS = {
    RawInformation: "market_intelligence",
    NormalizedInformation: "market_intelligence",
    Analysis: "market_intelligence",
    ValidatedTrend: "market_intelligence",
    ProductRequirement: "market_intelligence",
    ApplicationRequest: "application_interface",
    UserRequirement: "application_generation",
    ApplicationRecord: "application_engineering",
    EngineeringPlan: "application_engineering",
    EngineeringCheckpoint: "application_engineering",
    CodeChange: "application_engineering",
    BuildRecord: "application_engineering",
    TestRecord: "application_engineering",
    ReleaseRecord: "application_engineering",
    MaintenanceEvent: "application_engineering",
    RuntimeMetric: "application_runtime",
}


STRUCTURED_KNOWLEDGE_DATA_TYPE = (
    "structured_knowledge"
)


def encode_value(
    value: Any,
) -> Any:
    """
    Convert Evidence values into JSON-compatible values.

    UUIDs and datetimes are serialized as strings.
    Enums use their declared values.
    Dataclasses are recursively converted to dictionaries.
    """

    if isinstance(
        value,
        UUID,
    ):
        return str(
            value
        )

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    if isinstance(
        value,
        Enum,
    ):
        return encode_value(
            value.value
        )

    if dataclasses.is_dataclass(
        value
    ):
        return encode_value(
            dataclasses.asdict(
                value
            )
        )

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): encode_value(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            frozenset,
        ),
    ):
        return [
            encode_value(
                item
            )
            for item in value
        ]

    return value


def serialize_entity(
    entity: object,
) -> dict[str, Any]:
    """
    Serialize one Evidence entity into the normalized
    Data Engine Evidence envelope.

    Semantic identity is stored in sensor_type while
    data_type remains structured_knowledge.
    """

    entity_class = type(
        entity
    )

    entity_type = (
        ENTITY_TYPE_BY_CLASS.get(
            entity_class
        )
    )

    if entity_type is None:
        raise TypeError(
            "Unsupported Evidence entity class: "
            f"{entity_class.__name__}"
        )

    entity_id = getattr(
        entity,
        "id",
        None,
    )

    if not isinstance(
        entity_id,
        UUID,
    ):
        raise ValueError(
            "Evidence entity must contain "
            "a UUID id."
        )

    if not dataclasses.is_dataclass(
        entity
    ):
        raise TypeError(
            "Evidence entity must be "
            "a dataclass instance."
        )

    value = encode_value(
        dataclasses.asdict(
            entity
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise TypeError(
            "Serialized Evidence value "
            "must be a dictionary."
        )

    return {
        "id": str(
            entity_id
        ),
        "source": (
            ENTITY_SOURCE_BY_CLASS.get(
                entity_class,
                DEFAULT_ENTITY_SOURCE,
            )
        ),
        "data_type": (
            STRUCTURED_KNOWLEDGE_DATA_TYPE
        ),
        "sensor_type": (
            entity_type
        ),
        "value": value,
        "unit": "record",
    }


def _unwrap_optional(
    target_type: Any,
) -> tuple[
    bool,
    Any,
]:
    origin = get_origin(
        target_type
    )

    if origin not in {
        Union,
        types.UnionType,
    }:
        return (
            False,
            target_type,
        )

    arguments = get_args(
        target_type
    )

    non_none = tuple(
        argument
        for argument in arguments
        if argument is not type(
            None
        )
    )

    if (
        len(
            non_none
        )
        == 1
        and len(
            non_none
        )
        != len(
            arguments
        )
    ):
        return (
            True,
            non_none[
                0
            ],
        )

    return (
        False,
        target_type,
    )


def decode_value(
    value: Any,
    target_type: Any,
) -> Any:
    """
    Decode JSON-compatible Evidence values back into
    their declared Python field types.
    """

    optional, inner_type = (
        _unwrap_optional(
            target_type
        )
    )

    if optional:
        if value is None:
            return None

        return decode_value(
            value,
            inner_type,
        )

    if target_type is Any:
        return value

    if target_type is UUID:
        if isinstance(
            value,
            UUID,
        ):
            return value

        return UUID(
            str(
                value
            )
        )

    if target_type is datetime:
        if isinstance(
            value,
            datetime,
        ):
            return value

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "datetime value must "
                "be a string."
            )

        return datetime.fromisoformat(
            value
        )

    if (
        isinstance(
            target_type,
            type,
        )
        and issubclass(
            target_type,
            Enum,
        )
    ):
        return target_type(
            value
        )

    if (
        isinstance(
            target_type,
            type,
        )
        and dataclasses.is_dataclass(
            target_type
        )
    ):
        return _decode_dataclass(
            value,
            target_type,
        )

    origin = get_origin(
        target_type
    )

    arguments = get_args(
        target_type
    )

    if origin is list:
        if not isinstance(
            value,
            list,
        ):
            raise TypeError(
                "Expected a list value."
            )

        item_type = (
            arguments[
                0
            ]
            if arguments
            else Any
        )

        return [
            decode_value(
                item,
                item_type,
            )
            for item in value
        ]

    if origin is tuple:
        if not isinstance(
            value,
            (
                list,
                tuple,
            ),
        ):
            raise TypeError(
                "Expected a tuple-compatible value."
            )

        if not arguments:
            return tuple(
                value
            )

        if (
            len(
                arguments
            )
            == 2
            and arguments[
                1
            ]
            is Ellipsis
        ):
            item_type = (
                arguments[
                    0
                ]
            )

            return tuple(
                decode_value(
                    item,
                    item_type,
                )
                for item in value
            )

        return tuple(
            decode_value(
                item,
                item_type,
            )
            for item, item_type
            in zip(
                value,
                arguments,
                strict=False,
            )
        )

    if origin is dict:
        if not isinstance(
            value,
            dict,
        ):
            raise TypeError(
                "Expected a dictionary value."
            )

        key_type = (
            arguments[
                0
            ]
            if arguments
            else Any
        )

        value_type = (
            arguments[
                1
            ]
            if len(
                arguments
            )
            > 1
            else Any
        )

        return {
            decode_value(
                key,
                key_type,
            ): decode_value(
                item,
                value_type,
            )
            for key, item
            in value.items()
        }

    return value


def _decode_dataclass(
    value: Any,
    cls: type,
) -> Any:
    if not isinstance(
        value,
        dict,
    ):
        raise TypeError(
            f"{cls.__name__} value must "
            "be a dictionary."
        )

    type_hints = get_type_hints(
        cls
    )

    keyword_arguments: dict[
        str,
        Any,
    ] = {}

    for field in dataclasses.fields(
        cls
    ):
        if field.name not in value:
            continue

        field_type = (
            type_hints.get(
                field.name,
                field.type,
            )
        )

        keyword_arguments[
            field.name
        ] = decode_value(
            value[
                field.name
            ],
            field_type,
        )

    return cls(
        **keyword_arguments
    )


def deserialize_entity(
    record: dict[str, Any],
) -> object:
    """
    Reconstruct a registered Evidence entity from a
    normalized Data Engine Evidence record.
    """

    if not isinstance(
        record,
        dict,
    ):
        raise TypeError(
            "Evidence record must be "
            "a dictionary."
        )

    if (
        record.get(
            "data_type"
        )
        != STRUCTURED_KNOWLEDGE_DATA_TYPE
    ):
        raise ValueError(
            "Record is not structured knowledge."
        )

    entity_type = record.get(
        "sensor_type"
    )

    if not isinstance(
        entity_type,
        str,
    ):
        raise ValueError(
            "Evidence record does not contain "
            "a valid sensor_type."
        )

    entity_class = (
        ENTITY_CLASS_BY_TYPE.get(
            entity_type
        )
    )

    if entity_class is None:
        raise ValueError(
            "Unknown Evidence entity type: "
            f"{entity_type}"
        )

    value = record.get(
        "value"
    )

    entity = _decode_dataclass(
        value,
        entity_class,
    )

    entity_id = getattr(
        entity,
        "id",
        None,
    )

    record_id = record.get(
        "id"
    )

    if (
        record_id is not None
        and str(
            entity_id
        )
        != str(
            record_id
        )
    ):
        raise ValueError(
            "Evidence record ID does not match "
            "the serialized entity ID."
        )

    return entity
