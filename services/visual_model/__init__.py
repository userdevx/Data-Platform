"""Provider-independent boundaries for the private visual model service."""

from services.visual_model.backend_registry import (
    PrivateVisualBackendFactory,
    PrivateVisualBackendRegistry,
)
from services.visual_model.bootstrap import (
    VisualModelBootstrapConfiguration,
    VisualModelServiceAssembly,
    assemble_visual_model_service,
    load_visual_model_bootstrap_configuration,
    validate_visual_model_bootstrap_configuration,
)
from services.visual_model.config import (
    VisualModelServiceConfiguration,
    load_visual_model_service_configuration,
    validate_visual_model_service_configuration,
)
from services.visual_model.coordinator import (
    VisualModelCoordinator,
)
from services.visual_model.errors import (
    VisualModelBackendRegistrationError,
    VisualModelBootstrapError,
    VisualModelRequestValidationError,
    VisualModelResponseValidationError,
    VisualModelRuntimeError,
    VisualModelSerializationError,
    VisualModelServiceError,
    VisualModelTransportError,
)
from services.visual_model.providers.private_runtime import (
    PrivateVisualBackend,
    PrivateVisualBackendResult,
    PrivateVisualRuntime,
)
from services.visual_model.providers.runtime_config import (
    PRIVATE_VISUAL_RUNTIME_TYPE,
    PrivateVisualRuntimeConfiguration,
    load_private_visual_runtime_configuration,
    validate_private_visual_runtime_configuration,
)
from services.visual_model.requests import (
    VisualModelRequest,
)
from services.visual_model.responses import (
    VisualModelResponse,
)
from services.visual_model.runtime import (
    VisualModelRuntime,
    VisualRuntimeHealth,
)
from services.visual_model.runtime_factory import (
    build_visual_model_runtime,
)
from services.visual_model.serialization import (
    decode_json_payload,
    encode_json_payload,
    health_from_mapping,
    health_to_mapping,
    request_from_mapping,
    request_to_mapping,
    response_from_mapping,
    response_to_mapping,
)
from services.visual_model.service import (
    VisualModelService,
    VisualModelServiceResponse,
)
from services.visual_model.transport import (
    VisualModelTransportConfiguration,
    build_http_server,
    serve_forever,
    validate_transport_configuration,
)
from services.visual_model.validation import (
    validate_visual_model_request,
    validate_visual_model_response,
)


__all__ = [
    "PRIVATE_VISUAL_RUNTIME_TYPE",
    "PrivateVisualBackend",
    "PrivateVisualBackendFactory",
    "PrivateVisualBackendRegistry",
    "PrivateVisualBackendResult",
    "PrivateVisualRuntime",
    "PrivateVisualRuntimeConfiguration",
    "VisualModelBackendRegistrationError",
    "VisualModelBootstrapConfiguration",
    "VisualModelBootstrapError",
    "VisualModelCoordinator",
    "VisualModelRequest",
    "VisualModelRequestValidationError",
    "VisualModelResponse",
    "VisualModelResponseValidationError",
    "VisualModelRuntime",
    "VisualModelRuntimeError",
    "VisualModelSerializationError",
    "VisualModelService",
    "VisualModelServiceAssembly",
    "VisualModelServiceConfiguration",
    "VisualModelServiceError",
    "VisualModelServiceResponse",
    "VisualModelTransportConfiguration",
    "VisualModelTransportError",
    "VisualRuntimeHealth",
    "assemble_visual_model_service",
    "build_http_server",
    "build_visual_model_runtime",
    "decode_json_payload",
    "encode_json_payload",
    "health_from_mapping",
    "health_to_mapping",
    "load_private_visual_runtime_configuration",
    "load_visual_model_bootstrap_configuration",
    "load_visual_model_service_configuration",
    "request_from_mapping",
    "request_to_mapping",
    "response_from_mapping",
    "response_to_mapping",
    "serve_forever",
    "validate_private_visual_runtime_configuration",
    "validate_transport_configuration",
    "validate_visual_model_bootstrap_configuration",
    "validate_visual_model_request",
    "validate_visual_model_response",
    "validate_visual_model_service_configuration",
]
