from __future__ import annotations

import json
from uuid import uuid4

import pytest

from services.visual_model.config import (
    VisualModelServiceConfiguration,
)
from services.visual_model.coordinator import (
    VisualModelCoordinator,
)
from services.visual_model.errors import (
    VisualModelTransportError,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualRuntimeHealth,
)
from services.visual_model.serialization import (
    request_to_mapping,
)
from services.visual_model.service import (
    VisualModelService,
)
from services.visual_model.transport import (
    VisualModelTransportConfiguration,
    build_http_server,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class FakeRuntime:
    def health_check(
        self,
    ) -> VisualRuntimeHealth:
        return VisualRuntimeHealth(
            available=True,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            message="ready",
        )

    def analyze(
        self,
        request: VisualModelRequest,
    ) -> VisualModelResponse:
        return VisualModelResponse(
            request_id=request.request_id,
            provider=runtime_value(
                "provider"
            ),
            model_id=runtime_value(
                "model"
            ),
            scene_description=runtime_value(
                "description"
            ),
            duration_ms=1,
            validation_passed=True,
        )


def build_service() -> VisualModelService:
    coordinator = VisualModelCoordinator(
        runtime=FakeRuntime(),
        configuration=(
            VisualModelServiceConfiguration(
                enabled=True,
                maximum_image_size_bytes=1024,
                allowed_media_types=(
                    "image/png",
                ),
            )
        ),
    )

    return VisualModelService(
        coordinator=coordinator,
        maximum_request_payload_size_bytes=4096,
        maximum_response_payload_size_bytes=4096,
    )


def decode_response(
    payload: bytes,
) -> dict:
    return json.loads(
        payload.decode("utf-8")
    )


def test_health_operation() -> None:
    service = build_service()

    response = decode_response(
        service.handle_payload(
            b'{"operation":"health"}'
        )
    )

    assert response["status"] == "success"
    assert response["operation"] == "health"
    assert (
        response["data"]["health"]["available"]
        is True
    )


def test_analyze_operation() -> None:
    service = build_service()

    request = VisualModelRequest(
        request_id=runtime_value(
            "request"
        ),
        question=runtime_value(
            "question"
        ),
        image_data=b"image-data",
        media_type="image/png",
        response_schema={
            "type": "object",
        },
    )

    payload = json.dumps(
        {
            "operation": "analyze",
            "request": request_to_mapping(
                request
            ),
        }
    ).encode("utf-8")

    response = decode_response(
        service.handle_payload(payload)
    )

    assert response["status"] == "success"

    assert (
        response["data"]["response"][
            "request_id"
        ]
        == request.request_id
    )


def test_unknown_operation_is_rejected() -> None:
    response = decode_response(
        build_service().handle_payload(
            b'{"operation":"unknown"}'
        )
    )

    assert response["status"] == "rejected"
    assert response["errors"]


def test_health_rejects_request_object() -> None:
    response = decode_response(
        build_service().handle_payload(
            (
                b'{"operation":"health",'
                b'"request":{}}'
            )
        )
    )

    assert response["status"] == "rejected"


def test_analyze_requires_request() -> None:
    response = decode_response(
        build_service().handle_payload(
            b'{"operation":"analyze"}'
        )
    )

    assert response["status"] == "rejected"


@pytest.mark.parametrize(
    "host",
    [
        "0.0.0.0",
        "192.168.1.20",
        "example.com",
    ],
)
def test_non_loopback_host_is_rejected(
    host: str,
) -> None:
    with pytest.raises(
        VisualModelTransportError,
        match="loopback",
    ):
        VisualModelTransportConfiguration(
            host=host
        )


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "::1",
        "localhost",
    ],
)
def test_loopback_host_is_allowed(
    host: str,
) -> None:
    configuration = (
        VisualModelTransportConfiguration(
            host=host,
            port=0,
        )
    )

    assert configuration.host == host


def test_http_server_binds_to_loopback() -> None:
    configuration = (
        VisualModelTransportConfiguration(
            host="127.0.0.1",
            port=0,
        )
    )

    server = build_http_server(
        service=build_service(),
        configuration=configuration,
    )

    try:
        host, port = server.server_address

        assert host == "127.0.0.1"
        assert port > 0
    finally:
        server.server_close()
