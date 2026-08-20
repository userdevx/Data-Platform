from __future__ import annotations

import base64
from dataclasses import replace
from typing import Any
from urllib.parse import quote

from services.visual_model.provider_configuration import (
    VisualProviderConfiguration,
)
from services.visual_model.provider_contracts import (
    ModelStatus,
    VisualModelDescriptor,
    VisualProviderRequest,
    VisualProviderResult,
)
from services.visual_model.provider_errors import (
    VisualProviderResponseError,
)
from services.visual_model.provider_http import (
    request_json,
    resolve_credential,
)


class RemoteJsonVisualProvider:
    def __init__(
        self,
        configuration: VisualProviderConfiguration,
    ) -> None:
        self._configuration = configuration

    @property
    def provider_id(self) -> str:
        return self._configuration.provider_id

    def _headers(
        self,
    ) -> dict[str, str]:
        headers = dict(
            self._configuration.headers
        )

        credential = resolve_credential(
            self._configuration
            .credential_reference
        )

        if credential:
            headers[
                "Authorization"
            ] = f"Bearer {credential}"

        return headers

    def _url(
        self,
        path: str,
    ) -> str:
        return (
            f"{self._configuration.endpoint}"
            f"{path}"
        )

    def discover_models(
        self,
    ) -> tuple[VisualModelDescriptor, ...]:
        if not self._configuration.enabled:
            return ()

        if not self._configuration.discovery_path:
            return self._configuration.models

        response = request_json(
            method="GET",
            url=self._url(
                self._configuration.discovery_path
            ),
            timeout_seconds=(
                self._configuration.timeout_seconds
            ),
            headers=self._headers(),
        )

        raw_models = response.get("models")

        if not isinstance(raw_models, list):
            raise VisualProviderResponseError(
                "Model discovery must return "
                "a models array."
            )

        configured_by_id = {
            model.model_id: model
            for model in self._configuration.models
        }

        discovered: list[
            VisualModelDescriptor
        ] = []

        for index, raw_model in enumerate(
            raw_models
        ):
            if not isinstance(raw_model, dict):
                raise VisualProviderResponseError(
                    f"models[{index}] must "
                    "be an object."
                )

            model_id = raw_model.get("model_id")

            if not isinstance(
                model_id,
                str,
            ) or not model_id.strip():
                raise VisualProviderResponseError(
                    f"models[{index}].model_id "
                    "must be text."
                )

            configured = configured_by_id.get(
                model_id.strip()
            )

            if configured is None:
                continue

            status_text = raw_model.get(
                "status",
                ModelStatus.UNKNOWN.value,
            )

            try:
                status = ModelStatus(
                    str(status_text).strip().lower()
                )
            except ValueError:
                status = ModelStatus.UNKNOWN

            discovered.append(
                replace(
                    configured,
                    status=status,
                )
            )

        return tuple(discovered)

    def check_model_health(
        self,
        *,
        model_id: str,
    ) -> ModelStatus:
        if not self._configuration.enabled:
            return ModelStatus.DISABLED

        if not self._configuration.health_path:
            for model in self.discover_models():
                if model.model_id == model_id:
                    return model.status

            return ModelStatus.UNAVAILABLE

        model_path = (
            self._configuration.health_path
            .replace(
                "{model_id}",
                quote(
                    model_id,
                    safe="",
                ),
            )
        )

        response = request_json(
            method="GET",
            url=self._url(model_path),
            timeout_seconds=(
                self._configuration.timeout_seconds
            ),
            headers=self._headers(),
        )

        status_text = response.get(
            "status",
            ModelStatus.UNKNOWN.value,
        )

        try:
            return ModelStatus(
                str(status_text).strip().lower()
            )
        except ValueError:
            return ModelStatus.UNKNOWN

    def analyze(
        self,
        *,
        model_id: str,
        request: VisualProviderRequest,
    ) -> VisualProviderResult:
        if not self._configuration.analyze_path:
            raise VisualProviderResponseError(
                "The provider analyze path "
                "is not configured."
            )

        payload = {
            "request_id": request.request_id,
            "model_id": model_id,
            "input": {
                "question": request.question,
                "media_type": request.media_type,
                "image_base64": (
                    base64.b64encode(
                        request.image_data
                    ).decode("ascii")
                ),
            },
            "required_capabilities": sorted(
                request.required_capabilities
            ),
            "response_schema": dict(
                request.response_schema
            ),
            "generation": {
                "maximum_output_tokens": (
                    request
                    .maximum_output_tokens
                )
            },
        }

        response = request_json(
            method="POST",
            url=self._url(
                self._configuration.analyze_path
            ),
            timeout_seconds=(
                self._configuration.timeout_seconds
            ),
            headers=self._headers(),
            payload=payload,
        )

        if (
            str(
                response.get("status", "")
            ).strip().lower()
            != "success"
        ):
            raise VisualProviderResponseError(
                "The provider reported an "
                "analysis failure."
            )

        result = response.get("result")

        if not isinstance(result, dict):
            raise VisualProviderResponseError(
                "The provider result must "
                "be an object."
            )

        warnings_value = response.get(
            "warnings",
            [],
        )

        if not isinstance(
            warnings_value,
            list,
        ) or not all(
            isinstance(item, str)
            for item in warnings_value
        ):
            raise VisualProviderResponseError(
                "Provider warnings must "
                "be an array of text."
            )

        metadata = response.get(
            "metadata",
            {},
        )

        if not isinstance(metadata, dict):
            raise VisualProviderResponseError(
                "Provider metadata must "
                "be an object."
            )

        return VisualProviderResult(
            provider_id=self.provider_id,
            model_id=model_id,
            result=result,
            warnings=tuple(warnings_value),
            metadata=metadata,
        )
