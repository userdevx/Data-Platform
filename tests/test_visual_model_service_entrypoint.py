from __future__ import annotations

from services.visual_model import (
    VisualModelCoordinator,
    VisualModelRequest,
    VisualModelResponse,
    VisualModelRuntime,
    VisualModelSerializationError,
    VisualModelService,
    VisualModelTransportConfiguration,
    VisualModelTransportError,
    VisualRuntimeHealth,
    build_http_server,
    decode_json_payload,
    encode_json_payload,
    request_from_mapping,
    request_to_mapping,
    response_from_mapping,
    response_to_mapping,
)


def test_public_service_exports_exist() -> None:
    exports = (
        VisualModelCoordinator,
        VisualModelRequest,
        VisualModelResponse,
        VisualModelRuntime,
        VisualModelSerializationError,
        VisualModelService,
        VisualModelTransportConfiguration,
        VisualModelTransportError,
        VisualRuntimeHealth,
        build_http_server,
        decode_json_payload,
        encode_json_payload,
        request_from_mapping,
        request_to_mapping,
        response_from_mapping,
        response_to_mapping,
    )

    assert all(
        export is not None
        for export in exports
    )


def test_default_transport_is_loopback_only() -> None:
    configuration = (
        VisualModelTransportConfiguration()
    )

    assert configuration.host == "127.0.0.1"
    assert (
        configuration.service_path
        == "/v1/visual"
    )
