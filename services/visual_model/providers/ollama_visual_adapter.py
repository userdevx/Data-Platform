from __future__ import annotations

import base64
import json
from dataclasses import replace

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
)


class OllamaVisualProvider:
    def __init__(
        self,
        configuration: VisualProviderConfiguration,
    ) -> None:
        self._configuration = configuration

    @property
    def provider_id(self) -> str:
        return self._configuration.provider_id

    def _url(
        self,
        path: str,
    ) -> str:
        return (
            f"{self._configuration.endpoint}"
            f"{path}"
        )

    def _installed_model_ids(
        self,
    ) -> frozenset[str]:
        response = request_json(
            method="GET",
            url=self._url("/api/tags"),
            timeout_seconds=(
                self._configuration.timeout_seconds
            ),
            headers=(
                self._configuration.headers
            ),
        )

        raw_models = response.get("models")

        if not isinstance(raw_models, list):
            raise VisualProviderResponseError(
                "The local runtime catalog "
                "must contain a models array."
            )

        model_ids: set[str] = set()

        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                continue

            name = raw_model.get("name")

            if isinstance(
                name,
                str,
            ) and name.strip():
                model_ids.add(
                    name.strip()
                )

            model = raw_model.get("model")

            if isinstance(
                model,
                str,
            ) and model.strip():
                model_ids.add(
                    model.strip()
                )

        return frozenset(model_ids)

    def discover_models(
        self,
    ) -> tuple[VisualModelDescriptor, ...]:
        if not self._configuration.enabled:
            return ()

        installed = self._installed_model_ids()

        return tuple(
            replace(
                model,
                status=(
                    ModelStatus.AVAILABLE
                    if model.enabled
                    and model.model_id in installed
                    else ModelStatus.UNAVAILABLE
                ),
            )
            for model in self._configuration.models
        )

    def check_model_health(
        self,
        *,
        model_id: str,
    ) -> ModelStatus:
        if not self._configuration.enabled:
            return ModelStatus.DISABLED

        return (
            ModelStatus.AVAILABLE
            if model_id
            in self._installed_model_ids()
            else ModelStatus.UNAVAILABLE
        )

    def analyze(
        self,
        *,
        model_id: str,
        request: VisualProviderRequest,
    ) -> VisualProviderResult:
        payload = {
            "model": model_id,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": request.question,
                    "images": [
                        base64.b64encode(
                            request.image_data
                        ).decode("ascii")
                    ],
                }
            ],
            "options": {
                "num_predict": (
                    request
                    .maximum_output_tokens
                )
            },
        }

        if request.response_schema:
            payload["format"] = dict(
                request.response_schema
            )

        response = request_json(
            method="POST",
            url=self._url("/api/chat"),
            timeout_seconds=(
                self._configuration.timeout_seconds
            ),
            headers=(
                self._configuration.headers
            ),
            payload=payload,
        )

        message = response.get("message")

        if not isinstance(message, dict):
            raise VisualProviderResponseError(
                "The local runtime response "
                "is missing message."
            )

        content = message.get("content")

        if not isinstance(content, str):
            raise VisualProviderResponseError(
                "The local runtime response "
                "content must be text."
            )

        try:
            parsed_result = json.loads(content)
        except json.JSONDecodeError:
            parsed_result = {
                "text": content
            }

        if not isinstance(
            parsed_result,
            dict,
        ):
            parsed_result = {
                "value": parsed_result
            }

        return VisualProviderResult(
            provider_id=self.provider_id,
            model_id=model_id,
            result=parsed_result,
            metadata={
                "processing_location": "local",
                "runtime": "configured_local_runtime",
            },
        )
