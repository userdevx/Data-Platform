from __future__ import annotations

import base64
import json
from dataclasses import replace
from typing import Any

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
    VisualProviderError,
    VisualProviderResponseError,
)
from services.visual_model.provider_http import (
    request_json,
    resolve_credential,
)


class OpenAIResponsesVisualProvider:
    """OpenAI visual provider using the Responses API."""

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

    def _headers(
        self,
    ) -> dict[str, str]:
        credential = resolve_credential(
            self._configuration
            .credential_reference
        )

        return {
            **dict(
                self._configuration.headers
            ),
            "Authorization": (
                f"Bearer {credential}"
            ),
        }

    def _available_model_ids(
        self,
    ) -> frozenset[str]:
        response = request_json(
            method="GET",
            url=self._url("/v1/models"),
            timeout_seconds=(
                self._configuration
                .timeout_seconds
            ),
            headers=self._headers(),
        )

        raw_models = response.get("data")

        if not isinstance(raw_models, list):
            raise VisualProviderResponseError(
                "The OpenAI model response "
                "must contain a data array."
            )

        model_ids: set[str] = set()

        for raw_model in raw_models:
            if not isinstance(
                raw_model,
                dict,
            ):
                continue

            model_id = raw_model.get("id")

            if not isinstance(
                model_id,
                str,
            ):
                continue

            model_id = model_id.strip()

            if model_id:
                model_ids.add(model_id)

        return frozenset(model_ids)

    def discover_models(
        self,
    ) -> tuple[VisualModelDescriptor, ...]:
        if not self._configuration.enabled:
            return ()

        available_model_ids = (
            self._available_model_ids()
        )

        return tuple(
            replace(
                model,
                status=(
                    ModelStatus.AVAILABLE
                    if (
                        model.enabled
                        and model.model_id
                        in available_model_ids
                    )
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

        try:
            available_model_ids = (
                self._available_model_ids()
            )
        except VisualProviderError:
            return ModelStatus.UNHEALTHY

        if model_id in available_model_ids:
            return ModelStatus.AVAILABLE

        return ModelStatus.UNAVAILABLE

    def analyze(
        self,
        *,
        model_id: str,
        request: VisualProviderRequest,
    ) -> VisualProviderResult:
        encoded_image = base64.b64encode(
            request.image_data
        ).decode("ascii")

        image_url = (
            f"data:{request.media_type};"
            f"base64,{encoded_image}"
        )

        instruction = (
            request.question
            + "\n\nReturn only one valid JSON object."
        )

        if request.response_schema:
            instruction += (
                "\nFollow this JSON schema:\n"
                + json.dumps(
                    dict(
                        request.response_schema
                    ),
                    ensure_ascii=False,
                    allow_nan=False,
                )
            )

        payload: dict[str, Any] = {
            "model": model_id,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": instruction,
                        },
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": "auto",
                        },
                    ],
                }
            ],
            "max_output_tokens": (
                request.maximum_output_tokens
            ),
        }

        response = request_json(
            method="POST",
            url=self._url("/v1/responses"),
            timeout_seconds=(
                self._configuration
                .timeout_seconds
            ),
            headers=self._headers(),
            payload=payload,
        )

        output_text = _extract_output_text(
            response
        )

        try:
            parsed_result = json.loads(
                output_text
            )
        except json.JSONDecodeError as error:
            raise VisualProviderResponseError(
                "OpenAI returned invalid "
                "structured JSON."
            ) from error

        if not isinstance(
            parsed_result,
            dict,
        ):
            raise VisualProviderResponseError(
                "The OpenAI result must be "
                "a JSON object."
            )

        usage = response.get(
            "usage",
            {},
        )

        if not isinstance(usage, dict):
            usage = {}

        response_id = response.get(
            "id",
            "",
        )

        if not isinstance(response_id, str):
            response_id = ""

        return VisualProviderResult(
            provider_id=self.provider_id,
            model_id=model_id,
            result=parsed_result,
            metadata={
                "processing_location": "cloud",
                "response_id": response_id,
                "usage": usage,
            },
        )


def _extract_output_text(
    response: dict[str, Any],
) -> str:
    direct_output = response.get(
        "output_text"
    )

    if isinstance(
        direct_output,
        str,
    ) and direct_output.strip():
        return direct_output.strip()

    output = response.get("output")

    if not isinstance(output, list):
        raise VisualProviderResponseError(
            "The OpenAI response contains "
            "no output."
        )

    text_parts: list[str] = []

    for output_item in output:
        if not isinstance(
            output_item,
            dict,
        ):
            continue

        content = output_item.get(
            "content"
        )

        if not isinstance(content, list):
            continue

        for content_item in content:
            if not isinstance(
                content_item,
                dict,
            ):
                continue

            if content_item.get("type") not in {
                "output_text",
                "text",
            }:
                continue

            text = content_item.get("text")

            if isinstance(
                text,
                str,
            ) and text.strip():
                text_parts.append(
                    text.strip()
                )

    if not text_parts:
        raise VisualProviderResponseError(
            "OpenAI returned no response text."
        )

    return "\n".join(text_parts)
