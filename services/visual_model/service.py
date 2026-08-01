from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from services.visual_model.coordinator import (
    VisualModelCoordinator,
)
from services.visual_model.errors import (
    VisualModelRequestValidationError,
    VisualModelResponseValidationError,
    VisualModelRuntimeError,
    VisualModelSerializationError,
    VisualModelServiceError,
)
from services.visual_model.serialization import (
    decode_json_payload,
    encode_json_payload,
    health_to_mapping,
    request_from_mapping,
    response_to_mapping,
)


ENVELOPE_FIELDS = frozenset(
    {
        "operation",
        "request",
    }
)

SUPPORTED_OPERATIONS = frozenset(
    {
        "health",
        "analyze",
    }
)


@dataclass(frozen=True)
class VisualModelServiceResponse:
    status: str
    operation: str
    data: Mapping[str, Any]
    errors: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "operation": self.operation,
            "data": dict(self.data),
            "errors": list(self.errors),
        }


@dataclass
class VisualModelService:
    coordinator: VisualModelCoordinator
    maximum_request_payload_size_bytes: int
    maximum_response_payload_size_bytes: int

    def __post_init__(self) -> None:
        if (
            self.maximum_request_payload_size_bytes
            < 1
        ):
            raise ValueError(
                "maximum_request_payload_size_bytes "
                "must be positive."
            )

        if (
            self.maximum_response_payload_size_bytes
            < 1
        ):
            raise ValueError(
                "maximum_response_payload_size_bytes "
                "must be positive."
            )

    def handle_payload(
        self,
        payload: bytes,
    ) -> bytes:
        operation = "unknown"

        try:
            envelope = decode_json_payload(
                payload,
                maximum_payload_size_bytes=(
                    self
                    .maximum_request_payload_size_bytes
                ),
            )

            operation = self._read_operation(
                envelope
            )

            if operation == "health":
                result = self._handle_health(
                    envelope
                )
            elif operation == "analyze":
                result = self._handle_analyze(
                    envelope
                )
            else:
                raise VisualModelSerializationError(
                    "Unsupported operation."
                )

        except VisualModelSerializationError as error:
            result = VisualModelServiceResponse(
                status="rejected",
                operation=operation,
                data={},
                errors=(str(error),),
            )
        except VisualModelRequestValidationError as error:
            result = VisualModelServiceResponse(
                status="rejected",
                operation=operation,
                data={},
                errors=(str(error),),
            )
        except VisualModelResponseValidationError as error:
            result = VisualModelServiceResponse(
                status="invalid_response",
                operation=operation,
                data={},
                errors=(str(error),),
            )
        except VisualModelRuntimeError as error:
            result = VisualModelServiceResponse(
                status="runtime_error",
                operation=operation,
                data={},
                errors=(str(error),),
            )
        except VisualModelServiceError as error:
            result = VisualModelServiceResponse(
                status="service_error",
                operation=operation,
                data={},
                errors=(str(error),),
            )
        except Exception:
            result = VisualModelServiceResponse(
                status="internal_error",
                operation=operation,
                data={},
                errors=(
                    "The visual model service "
                    "encountered an internal error.",
                ),
            )

        return encode_json_payload(
            result.to_mapping(),
            maximum_payload_size_bytes=(
                self
                .maximum_response_payload_size_bytes
            ),
        )

    def _read_operation(
        self,
        envelope: Mapping[str, Any],
    ) -> str:
        unknown_fields = (
            set(envelope)
            - ENVELOPE_FIELDS
        )

        if unknown_fields:
            names = ", ".join(
                sorted(unknown_fields)
            )

            raise VisualModelSerializationError(
                "payload contains unknown fields: "
                f"{names}"
            )

        operation = envelope.get(
            "operation"
        )

        if not isinstance(operation, str):
            raise VisualModelSerializationError(
                "payload.operation must be text."
            )

        operation = operation.strip().lower()

        if operation not in SUPPORTED_OPERATIONS:
            raise VisualModelSerializationError(
                f"Unsupported operation: {operation}"
            )

        return operation

    def _handle_health(
        self,
        envelope: Mapping[str, Any],
    ) -> VisualModelServiceResponse:
        if "request" in envelope:
            raise VisualModelSerializationError(
                "The health operation does not accept "
                "a request object."
            )

        health = self.coordinator.health_check()

        return VisualModelServiceResponse(
            status="success",
            operation="health",
            data={
                "health": health_to_mapping(
                    health
                ),
            },
        )

    def _handle_analyze(
        self,
        envelope: Mapping[str, Any],
    ) -> VisualModelServiceResponse:
        if "request" not in envelope:
            raise VisualModelSerializationError(
                "The analyze operation requires "
                "a request object."
            )

        request_value = envelope[
            "request"
        ]

        if not isinstance(
            request_value,
            Mapping,
        ):
            raise VisualModelSerializationError(
                "payload.request must be an object."
            )

        request = request_from_mapping(
            request_value
        )

        response = self.coordinator.analyze(
            request
        )

        return VisualModelServiceResponse(
            status="success",
            operation="analyze",
            data={
                "response": response_to_mapping(
                    response
                ),
            },
        )
