from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from services.visual_model.errors import (
    VisualModelRuntimeError,
)
from services.visual_model.providers.private_runtime import (
    PrivateVisualBackendResult,
)


DEFAULT_MAXIMUM_RESPONSE_SIZE_BYTES = (
    10 * 1024 * 1024
)


def _immutable_environment(
    value: Mapping[str, str],
) -> Mapping[str, str]:
    return MappingProxyType(
        {
            str(key): str(item)
            for key, item in value.items()
        }
    )


@dataclass(frozen=True)
class LocalProcessVisualBackendConfiguration:
    executable_path: str
    arguments: tuple[str, ...] = ()
    working_directory: str = ""
    environment: Mapping[str, str] = field(
        default_factory=dict
    )
    maximum_response_size_bytes: int = (
        DEFAULT_MAXIMUM_RESPONSE_SIZE_BYTES
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "executable_path",
            self.executable_path.strip(),
        )
        object.__setattr__(
            self,
            "arguments",
            tuple(
                str(argument)
                for argument in self.arguments
            ),
        )
        object.__setattr__(
            self,
            "working_directory",
            self.working_directory.strip(),
        )
        object.__setattr__(
            self,
            "environment",
            _immutable_environment(
                self.environment
            ),
        )

        validate_local_process_backend_configuration(
            self
        )


def validate_local_process_backend_configuration(
    configuration: LocalProcessVisualBackendConfiguration,
) -> None:
    if not configuration.executable_path:
        raise ValueError(
            "executable_path is required."
        )

    if configuration.maximum_response_size_bytes < 1:
        raise ValueError(
            "maximum_response_size_bytes "
            "must be positive."
        )


def _require_mapping(
    value: Any,
    *,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VisualModelRuntimeError(
            f"{field_name} must be an object."
        )

    return value


def _require_string(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise VisualModelRuntimeError(
            f"{field_name} must be text."
        )

    return value


def _optional_string_list(
    value: Any,
    *,
    field_name: str,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if not isinstance(value, list):
        raise VisualModelRuntimeError(
            f"{field_name} must be an array."
        )

    result: list[str] = []

    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise VisualModelRuntimeError(
                f"{field_name}[{index}] "
                "must be text."
            )

        clean_item = item.strip()

        if clean_item:
            result.append(clean_item)

    return tuple(result)


def _optional_mapping_list(
    value: Any,
    *,
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()

    if not isinstance(value, list):
        raise VisualModelRuntimeError(
            f"{field_name} must be an array."
        )

    result: list[Mapping[str, Any]] = []

    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise VisualModelRuntimeError(
                f"{field_name}[{index}] "
                "must be an object."
            )

        result.append(
            dict(item)
        )

    return tuple(result)


@dataclass
class LocalProcessVisualBackend:
    configuration: (
        LocalProcessVisualBackendConfiguration
    )
    _model_path: Path | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _model_id: str = field(
        default="",
        init=False,
        repr=False,
    )
    _available: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    def initialize(
        self,
        *,
        model_path: Path,
        model_id: str,
        initialization_timeout_seconds: int,
    ) -> None:
        del initialization_timeout_seconds

        executable_path = Path(
            self.configuration.executable_path
        ).expanduser().resolve()

        if not executable_path.exists():
            raise VisualModelRuntimeError(
                "The local visual backend "
                "executable does not exist."
            )

        if not executable_path.is_file():
            raise VisualModelRuntimeError(
                "The local visual backend "
                "executable must reference a file."
            )

        if not os.access(
            executable_path,
            os.X_OK,
        ):
            raise VisualModelRuntimeError(
                "The local visual backend "
                "executable is not executable."
            )

        if not model_path.exists():
            raise VisualModelRuntimeError(
                "The configured visual model "
                "file does not exist."
            )

        if not model_path.is_file():
            raise VisualModelRuntimeError(
                "The configured visual model "
                "path must reference a file."
            )

        if self.configuration.working_directory:
            working_directory = Path(
                self.configuration
                .working_directory
            ).expanduser().resolve()

            if not working_directory.exists():
                raise VisualModelRuntimeError(
                    "The local visual backend "
                    "working directory does not exist."
                )

            if not working_directory.is_dir():
                raise VisualModelRuntimeError(
                    "The local visual backend "
                    "working directory must be a directory."
                )

        self._model_path = model_path.resolve()
        self._model_id = model_id.strip()
        self._available = True

    def is_available(self) -> bool:
        return (
            self._available
            and self._model_path is not None
        )

    def analyze(
        self,
        *,
        question: str,
        image_data: bytes,
        media_type: str,
        response_schema: Mapping[str, Any],
        maximum_output_tokens: int,
        inference_timeout_seconds: int,
    ) -> PrivateVisualBackendResult:
        if not self.is_available():
            raise VisualModelRuntimeError(
                "The local visual backend "
                "has not been initialized."
            )

        if self._model_path is None:
            raise VisualModelRuntimeError(
                "The local visual model path "
                "is unavailable."
            )

        request_payload = {
            "operation": "analyze",
            "model": {
                "id": self._model_id,
                "path": str(
                    self._model_path
                ),
            },
            "input": {
                "question": question,
                "media_type": media_type,
                "image_base64": (
                    base64.b64encode(
                        image_data
                    ).decode("ascii")
                ),
            },
            "generation": {
                "maximum_output_tokens": (
                    maximum_output_tokens
                ),
            },
            "response_schema": dict(
                response_schema
            ),
        }

        try:
            encoded_request = json.dumps(
                request_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (
            TypeError,
            ValueError,
        ) as error:
            raise VisualModelRuntimeError(
                "The local visual backend "
                "request could not be encoded."
            ) from error

        command = [
            self.configuration.executable_path,
            *self.configuration.arguments,
        ]

        environment = os.environ.copy()
        environment.update(
            self.configuration.environment
        )

        working_directory = (
            self.configuration.working_directory
            or None
        )

        try:
            completed = subprocess.run(
                command,
                input=encoded_request,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=inference_timeout_seconds,
                check=False,
                cwd=working_directory,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise VisualModelRuntimeError(
                "The local visual backend "
                "timed out during inference."
            ) from error
        except OSError as error:
            raise VisualModelRuntimeError(
                "The local visual backend "
                "process could not be started."
            ) from error

        if completed.returncode != 0:
            raise VisualModelRuntimeError(
                "The local visual backend "
                "process returned a failure status."
            )

        if not completed.stdout:
            raise VisualModelRuntimeError(
                "The local visual backend "
                "returned an empty response."
            )

        if (
            len(completed.stdout)
            > self.configuration
            .maximum_response_size_bytes
        ):
            raise VisualModelRuntimeError(
                "The local visual backend "
                "response exceeded the maximum size."
            )

        try:
            decoded_response = json.loads(
                completed.stdout.decode(
                    "utf-8"
                )
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise VisualModelRuntimeError(
                "The local visual backend "
                "returned invalid JSON."
            ) from error

        response = _require_mapping(
            decoded_response,
            field_name="backend response",
        )

        status = _require_string(
            response.get("status"),
            field_name="backend response.status",
        ).strip().lower()

        if status != "success":
            raise VisualModelRuntimeError(
                "The local visual backend "
                "reported an inference failure."
            )

        result = _require_mapping(
            response.get("result"),
            field_name="backend response.result",
        )

        metadata_value = result.get(
            "metadata",
            {},
        )

        metadata = _require_mapping(
            metadata_value,
            field_name=(
                "backend response.result.metadata"
            ),
        )

        return PrivateVisualBackendResult(
            scene_description=_require_string(
                result.get(
                    "scene_description",
                    "",
                ),
                field_name=(
                    "backend response.result."
                    "scene_description"
                ),
            ),
            entities=_optional_mapping_list(
                result.get("entities"),
                field_name=(
                    "backend response.result.entities"
                ),
            ),
            relations=_optional_mapping_list(
                result.get("relations"),
                field_name=(
                    "backend response.result.relations"
                ),
            ),
            visible_text=_optional_string_list(
                result.get("visible_text"),
                field_name=(
                    "backend response.result."
                    "visible_text"
                ),
            ),
            uncertainty=_optional_string_list(
                result.get("uncertainty"),
                field_name=(
                    "backend response.result."
                    "uncertainty"
                ),
            ),
            warnings=_optional_string_list(
                result.get("warnings"),
                field_name=(
                    "backend response.result.warnings"
                ),
            ),
            metadata=dict(metadata),
        )
