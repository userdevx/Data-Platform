from __future__ import annotations

from dataclasses import dataclass
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Type

from services.visual_model.errors import (
    VisualModelTransportError,
)
from services.visual_model.service import (
    VisualModelService,
)


LOOPBACK_HOSTS = frozenset(
    {
        "127.0.0.1",
        "::1",
        "localhost",
    }
)

DEFAULT_SERVICE_PATH = "/v1/visual"


@dataclass(frozen=True)
class VisualModelTransportConfiguration:
    host: str = "127.0.0.1"
    port: int = 8765
    service_path: str = DEFAULT_SERVICE_PATH
    maximum_request_payload_size_bytes: int = (
        25 * 1024 * 1024
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "host",
            self.host.strip().lower(),
        )

        service_path = (
            self.service_path.strip()
        )

        if not service_path.startswith("/"):
            service_path = (
                f"/{service_path}"
            )

        object.__setattr__(
            self,
            "service_path",
            service_path,
        )

        validate_transport_configuration(
            self
        )


def validate_transport_configuration(
    configuration: VisualModelTransportConfiguration,
) -> None:
    if configuration.host not in LOOPBACK_HOSTS:
        raise VisualModelTransportError(
            "The visual model service may bind "
            "only to a loopback host."
        )

    if not 0 <= configuration.port <= 65535:
        raise VisualModelTransportError(
            "The transport port must be between "
            "0 and 65535."
        )

    if (
        configuration
        .maximum_request_payload_size_bytes
        < 1
    ):
        raise VisualModelTransportError(
            "maximum_request_payload_size_bytes "
            "must be positive."
        )

    if not configuration.service_path:
        raise VisualModelTransportError(
            "service_path is required."
        )


def create_request_handler(
    *,
    service: VisualModelService,
    configuration: VisualModelTransportConfiguration,
) -> Type[BaseHTTPRequestHandler]:
    class VisualModelRequestHandler(
        BaseHTTPRequestHandler
    ):
        server_version = (
            "DataPlatformVisualModel/1"
        )

        def do_POST(self) -> None:
            if self.path != (
                configuration.service_path
            ):
                self._send_json(
                    status_code=404,
                    payload=(
                        b'{"status":"not_found",'
                        b'"operation":"unknown",'
                        b'"data":{},'
                        b'"errors":["Route not found."]}'
                    ),
                )
                return

            content_type = self.headers.get(
                "Content-Type",
                "",
            ).split(
                ";",
                maxsplit=1,
            )[0].strip().lower()

            if content_type != "application/json":
                self._send_json(
                    status_code=415,
                    payload=(
                        b'{"status":"rejected",'
                        b'"operation":"unknown",'
                        b'"data":{},'
                        b'"errors":["Content-Type must be '
                        b'application/json."]}'
                    ),
                )
                return

            content_length_text = (
                self.headers.get(
                    "Content-Length"
                )
            )

            if content_length_text is None:
                self._send_json(
                    status_code=411,
                    payload=(
                        b'{"status":"rejected",'
                        b'"operation":"unknown",'
                        b'"data":{},'
                        b'"errors":["Content-Length is required."]}'
                    ),
                )
                return

            try:
                content_length = int(
                    content_length_text
                )
            except ValueError:
                self._send_json(
                    status_code=400,
                    payload=(
                        b'{"status":"rejected",'
                        b'"operation":"unknown",'
                        b'"data":{},'
                        b'"errors":["Content-Length is invalid."]}'
                    ),
                )
                return

            if content_length < 1:
                self._send_json(
                    status_code=400,
                    payload=(
                        b'{"status":"rejected",'
                        b'"operation":"unknown",'
                        b'"data":{},'
                        b'"errors":["Request body is required."]}'
                    ),
                )
                return

            if content_length > (
                configuration
                .maximum_request_payload_size_bytes
            ):
                self._send_json(
                    status_code=413,
                    payload=(
                        b'{"status":"rejected",'
                        b'"operation":"unknown",'
                        b'"data":{},'
                        b'"errors":["Request payload is too large."]}'
                    ),
                )
                return

            payload = self.rfile.read(
                content_length
            )

            response_payload = (
                service.handle_payload(
                    payload
                )
            )

            self._send_json(
                status_code=200,
                payload=response_payload,
            )

        def do_GET(self) -> None:
            self._send_json(
                status_code=405,
                payload=(
                    b'{"status":"rejected",'
                    b'"operation":"unknown",'
                    b'"data":{},'
                    b'"errors":["Use POST for service operations."]}'
                ),
            )

        def log_message(
            self,
            format: str,
            *args,
        ) -> None:
            del format
            del args

        def _send_json(
            self,
            *,
            status_code: int,
            payload: bytes,
        ) -> None:
            self.send_response(
                status_code
            )
            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(len(payload)),
            )
            self.send_header(
                "Cache-Control",
                "no-store",
            )
            self.end_headers()
            self.wfile.write(payload)

    return VisualModelRequestHandler


def build_http_server(
    *,
    service: VisualModelService,
    configuration: VisualModelTransportConfiguration,
) -> ThreadingHTTPServer:
    validate_transport_configuration(
        configuration
    )

    handler = create_request_handler(
        service=service,
        configuration=configuration,
    )

    try:
        return ThreadingHTTPServer(
            (
                configuration.host,
                configuration.port,
            ),
            handler,
        )
    except OSError as error:
        raise VisualModelTransportError(
            "The private visual model transport "
            "could not bind to the configured address."
        ) from error


def serve_forever(
    *,
    service: VisualModelService,
    configuration: VisualModelTransportConfiguration,
) -> None:
    server = build_http_server(
        service=service,
        configuration=configuration,
    )

    try:
        server.serve_forever(
            poll_interval=0.5
        )
    finally:
        server.server_close()
