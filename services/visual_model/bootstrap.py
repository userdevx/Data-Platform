from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.visual_model.backend_registry import (
    PrivateVisualBackendRegistry,
)
from services.visual_model.config import (
    VisualModelServiceConfiguration,
    load_visual_model_service_configuration,
)
from services.visual_model.coordinator import (
    VisualModelCoordinator,
)
from services.visual_model.errors import (
    VisualModelBackendRegistrationError,
    VisualModelBootstrapError,
    VisualModelTransportError,
)
from services.visual_model.providers.runtime_config import (
    PrivateVisualRuntimeConfiguration,
    load_private_visual_runtime_configuration,
)
from services.visual_model.runtime_factory import (
    build_visual_model_runtime,
)
from services.visual_model.service import (
    VisualModelService,
)
from services.visual_model.transport import (
    VisualModelTransportConfiguration,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

DEFAULT_RUNTIME_CONFIGURATION_PATH = (
    PROJECT_ROOT
    / "config"
    / "visual_model"
    / "active.json"
)

DEFAULT_SERVICE_CONFIGURATION_PATH = (
    PROJECT_ROOT
    / "config"
    / "visual_model"
    / "service.json"
)


@dataclass(frozen=True)
class VisualModelBootstrapConfiguration:
    backend_name: str
    host: str
    port: int
    service_path: str
    maximum_request_payload_size_bytes: int
    maximum_response_payload_size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "backend_name",
            self.backend_name.strip().lower(),
        )
        object.__setattr__(
            self,
            "host",
            self.host.strip().lower(),
        )

        service_path = self.service_path.strip()

        if not service_path.startswith("/"):
            service_path = f"/{service_path}"

        object.__setattr__(
            self,
            "service_path",
            service_path,
        )


@dataclass(frozen=True)
class VisualModelServiceAssembly:
    runtime_configuration: (
        PrivateVisualRuntimeConfiguration
    )
    service_configuration: (
        VisualModelServiceConfiguration
    )
    bootstrap_configuration: (
        VisualModelBootstrapConfiguration
    )
    coordinator: VisualModelCoordinator
    service: VisualModelService
    transport_configuration: (
        VisualModelTransportConfiguration
    )


def _require_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{field_name} must be an object."
        )

    return value


def _require_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be text."
        )

    return value


def _require_integer(
    value: Any,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be an integer."
        ) from error


def validate_visual_model_bootstrap_configuration(
    configuration: VisualModelBootstrapConfiguration,
) -> None:
    if not configuration.host:
        raise ValueError(
            "host is required."
        )

    if not 0 <= configuration.port <= 65535:
        raise ValueError(
            "port must be between 0 and 65535."
        )

    if not configuration.service_path:
        raise ValueError(
            "service_path is required."
        )

    if (
        configuration
        .maximum_request_payload_size_bytes
        < 1
    ):
        raise ValueError(
            "maximum_request_payload_size_bytes "
            "must be positive."
        )

    if (
        configuration
        .maximum_response_payload_size_bytes
        < 1
    ):
        raise ValueError(
            "maximum_response_payload_size_bytes "
            "must be positive."
        )


def load_visual_model_bootstrap_configuration(
    path: Path,
) -> VisualModelBootstrapConfiguration:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    root = _require_mapping(
        payload.get("visual_model_transport"),
        field_name="visual_model_transport",
    )

    configuration = (
        VisualModelBootstrapConfiguration(
            backend_name=_require_text(
                root.get("backend_name", ""),
                field_name=(
                    "visual_model_transport."
                    "backend_name"
                ),
            ),
            host=_require_text(
                root.get(
                    "host",
                    "127.0.0.1",
                ),
                field_name=(
                    "visual_model_transport.host"
                ),
            ),
            port=_require_integer(
                root.get("port", 8765),
                field_name=(
                    "visual_model_transport.port"
                ),
            ),
            service_path=_require_text(
                root.get(
                    "service_path",
                    "/v1/visual",
                ),
                field_name=(
                    "visual_model_transport."
                    "service_path"
                ),
            ),
            maximum_request_payload_size_bytes=(
                _require_integer(
                    root.get(
                        (
                            "maximum_request_payload_"
                            "size_bytes"
                        ),
                        25 * 1024 * 1024,
                    ),
                    field_name=(
                        "visual_model_transport."
                        "maximum_request_payload_"
                        "size_bytes"
                    ),
                )
            ),
            maximum_response_payload_size_bytes=(
                _require_integer(
                    root.get(
                        (
                            "maximum_response_payload_"
                            "size_bytes"
                        ),
                        10 * 1024 * 1024,
                    ),
                    field_name=(
                        "visual_model_transport."
                        "maximum_response_payload_"
                        "size_bytes"
                    ),
                )
            ),
        )
    )

    validate_visual_model_bootstrap_configuration(
        configuration
    )

    return configuration


def assemble_visual_model_service(
    *,
    backend_registry: PrivateVisualBackendRegistry,
    runtime_configuration_path: Path = (
        DEFAULT_RUNTIME_CONFIGURATION_PATH
    ),
    service_configuration_path: Path = (
        DEFAULT_SERVICE_CONFIGURATION_PATH
    ),
) -> VisualModelServiceAssembly:
    try:
        runtime_configuration = (
            load_private_visual_runtime_configuration(
                runtime_configuration_path
            )
        )

        service_configuration = (
            load_visual_model_service_configuration(
                service_configuration_path
            )
        )

        bootstrap_configuration = (
            load_visual_model_bootstrap_configuration(
                service_configuration_path
            )
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise VisualModelBootstrapError(
            "The visual model service "
            "configuration could not be loaded."
        ) from error

    backend_name = (
        bootstrap_configuration.backend_name
    )

    if not runtime_configuration.enabled:
        backend_name = (
            backend_name
            or "__disabled_runtime__"
        )

    try:
        if runtime_configuration.enabled:
            backend = backend_registry.create(
                backend_name
            )
        else:
            backend = _DisabledPrivateVisualBackend()
    except VisualModelBackendRegistrationError as error:
        raise VisualModelBootstrapError(
            "The configured private visual backend "
            "could not be created."
        ) from error

    runtime = build_visual_model_runtime(
        configuration=runtime_configuration,
        backend_factory=lambda: backend,
    )

    coordinator = VisualModelCoordinator(
        runtime=runtime,
        configuration=service_configuration,
    )

    service = VisualModelService(
        coordinator=coordinator,
        maximum_request_payload_size_bytes=(
            bootstrap_configuration
            .maximum_request_payload_size_bytes
        ),
        maximum_response_payload_size_bytes=(
            bootstrap_configuration
            .maximum_response_payload_size_bytes
        ),
    )

    try:
        transport_configuration = (
            VisualModelTransportConfiguration(
                host=bootstrap_configuration.host,
                port=bootstrap_configuration.port,
                service_path=(
                    bootstrap_configuration.service_path
                ),
                maximum_request_payload_size_bytes=(
                    bootstrap_configuration
                    .maximum_request_payload_size_bytes
                ),
            )
        )
    except VisualModelTransportError as error:
        raise VisualModelBootstrapError(
            "The visual model transport "
            "configuration is invalid."
        ) from error

    return VisualModelServiceAssembly(
        runtime_configuration=(
            runtime_configuration
        ),
        service_configuration=(
            service_configuration
        ),
        bootstrap_configuration=(
            bootstrap_configuration
        ),
        coordinator=coordinator,
        service=service,
        transport_configuration=(
            transport_configuration
        ),
    )


class _DisabledPrivateVisualBackend:
    def initialize(
        self,
        *,
        model_path: Path,
        model_id: str,
        initialization_timeout_seconds: int,
    ) -> None:
        del model_path
        del model_id
        del initialization_timeout_seconds

    def is_available(self) -> bool:
        return False

    def analyze(
        self,
        *,
        question: str,
        image_data: bytes,
        media_type: str,
        response_schema,
        maximum_output_tokens: int,
        inference_timeout_seconds: int,
    ):
        del question
        del image_data
        del media_type
        del response_schema
        del maximum_output_tokens
        del inference_timeout_seconds

        raise RuntimeError(
            "The disabled backend cannot perform inference."
        )
