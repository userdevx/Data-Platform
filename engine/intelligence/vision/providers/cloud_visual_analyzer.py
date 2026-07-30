from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CloudVisualAnalyzerError(RuntimeError):
    """Raised when cloud visual analysis cannot be completed."""


@dataclass(frozen=True)
class CloudVisualAnalyzerConfig:
    provider: str
    model: str
    endpoint_url: str
    api_key_env_var: str
    request_timeout_seconds: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError(
                "A cloud visual provider is required."
            )

        if not self.model.strip():
            raise ValueError(
                "A cloud visual model is required."
            )

        if not self.endpoint_url.strip():
            raise ValueError(
                "A cloud visual endpoint URL is required."
            )

        if not self.api_key_env_var.strip():
            raise ValueError(
                "An API key environment-variable name is required."
            )

        if self.request_timeout_seconds < 1:
            raise ValueError(
                "request_timeout_seconds must be positive."
            )

        if self.max_output_tokens < 1:
            raise ValueError(
                "max_output_tokens must be positive."
            )


class CloudVisualAnalyzer:
    """
    Provider adapter for cloud-based visual analysis.

    Responsibilities:
    - validate and encode an image on the device;
    - send the image to a configured multimodal endpoint;
    - require a generic structured response;
    - normalize the response without fixed visual label catalogs.
    """

    def __init__(
        self,
        config: CloudVisualAnalyzerConfig,
    ) -> None:
        self.config = config

    def analyze(
        self,
        *,
        question: str,
        image_path: str,
        source_uri: str | None = None,
    ) -> dict[str, Any]:
        clean_question = question.strip()

        if not clean_question:
            raise CloudVisualAnalyzerError(
                "A visual analysis question is required."
            )

        api_key = os.environ.get(
            self.config.api_key_env_var,
            "",
        ).strip()

        if not api_key:
            raise CloudVisualAnalyzerError(
                "The visual provider API key is missing. "
                f"Set {self.config.api_key_env_var}."
            )

        image_file = Path(
            image_path
        ).expanduser().resolve()

        if not image_file.is_file():
            raise CloudVisualAnalyzerError(
                f"Image file was not found: {image_file}"
            )

        mime_type = self._resolve_mime_type(
            image_file
        )

        encoded_image = base64.b64encode(
            image_file.read_bytes()
        ).decode("ascii")

        payload = self._build_payload(
            question=clean_question,
            encoded_image=encoded_image,
            mime_type=mime_type,
        )

        response_json = self._post_json(
            url=self.config.endpoint_url,
            api_key=api_key,
            payload=payload,
        )

        provider_json = (
            self._extract_structured_json(
                response_json
            )
        )

        return self._normalize_provider_response(
            question=clean_question,
            image_path=str(image_file),
            source_uri=source_uri,
            provider_json=provider_json,
        )

    def _build_payload(
        self,
        *,
        question: str,
        encoded_image: str,
        mime_type: str,
    ) -> dict[str, Any]:
        provider = (
            self.config.provider
            .strip()
            .lower()
        )

        if provider != "openai":
            raise CloudVisualAnalyzerError(
                "Unsupported visual cloud provider: "
                f"{self.config.provider}"
            )

        system_instruction = (
            "Analyze the supplied image according to the user's request. "
            "Use open-vocabulary observations generated from the visible "
            "evidence at runtime. "
            "Do not rely on fixed application object, action, product, "
            "person, event, or scene catalogs. "
            "Do not infer a person's identity from appearance. "
            "Do not invent details that are not visibly supported. "
            "Return uncertainty when the evidence is incomplete. "
            "Every relation must reference entity identifiers returned "
            "in the entities array. "
            "Return only data matching the required JSON schema."
        )

        user_instruction = (
            "Visual analysis request:\n"
            f"{question}"
        )

        return {
            "model": self.config.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_instruction,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_instruction,
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{mime_type};"
                                f"base64,{encoded_image}"
                            ),
                        },
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "visual_observation",
                    "strict": True,
                    "schema": self._response_schema(),
                }
            },
            "max_output_tokens": (
                self.config.max_output_tokens
            ),
        }

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "scene_description": {
                    "type": "string",
                },
                "visible_text": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "entity_id": {
                                "type": "string",
                            },
                            "label": {
                                "type": "string",
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "attributes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                        },
                                        "value": {
                                            "type": "string",
                                        },
                                        "confidence": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 1,
                                        },
                                    },
                                    "required": [
                                        "name",
                                        "value",
                                        "confidence",
                                    ],
                                },
                            },
                            "states": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                        },
                        "required": [
                            "entity_id",
                            "label",
                            "confidence",
                            "attributes",
                            "states",
                        ],
                    },
                },
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "relation_id": {
                                "type": "string",
                            },
                            "subject_entity_id": {
                                "type": "string",
                            },
                            "predicate": {
                                "type": "string",
                            },
                            "object_entity_id": {
                                "type": "string",
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": [
                            "relation_id",
                            "subject_entity_id",
                            "predicate",
                            "object_entity_id",
                            "confidence",
                        ],
                    },
                },
                "uncertainties": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "required": [
                "scene_description",
                "visible_text",
                "entities",
                "relations",
                "uncertainties",
            ],
        }

    def _post_json(
        self,
        *,
        url: str,
        api_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            url=url,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Authorization": (
                    f"Bearer {api_key}"
                ),
                "Content-Type": (
                    "application/json"
                ),
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=(
                    self.config
                    .request_timeout_seconds
                ),
            ) as response:
                body = response.read().decode(
                    "utf-8"
                )

        except HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise CloudVisualAnalyzerError(
                "The visual provider rejected "
                f"the request with HTTP {error.code}: "
                f"{error_body}"
            ) from error

        except URLError as error:
            raise CloudVisualAnalyzerError(
                "The visual provider could not "
                f"be reached: {error.reason}"
            ) from error

        except TimeoutError as error:
            raise CloudVisualAnalyzerError(
                "The visual provider request timed out."
            ) from error

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as error:
            raise CloudVisualAnalyzerError(
                "The visual provider returned "
                "invalid response JSON."
            ) from error

        if not isinstance(parsed, dict):
            raise CloudVisualAnalyzerError(
                "The visual provider response "
                "must be a JSON object."
            )

        return parsed

    def _extract_structured_json(
        self,
        response_json: dict[str, Any],
    ) -> dict[str, Any]:
        provider = (
            self.config.provider
            .strip()
            .lower()
        )

        if provider != "openai":
            raise CloudVisualAnalyzerError(
                "Unsupported visual cloud provider: "
                f"{self.config.provider}"
            )

        response_error = response_json.get(
            "error"
        )

        if response_error:
            raise CloudVisualAnalyzerError(
                "The visual provider returned an error: "
                f"{response_error}"
            )

        output_text = response_json.get(
            "output_text"
        )

        if (
            isinstance(output_text, str)
            and output_text.strip()
        ):
            return self._parse_json_text(
                output_text
            )

        output = response_json.get(
            "output",
            [],
        )

        if not isinstance(output, list):
            raise CloudVisualAnalyzerError(
                "The provider output field "
                "must be an array."
            )

        for output_item in output:
            if not isinstance(
                output_item,
                dict,
            ):
                continue

            content = output_item.get(
                "content",
                [],
            )

            if not isinstance(content, list):
                continue

            for content_item in content:
                if not isinstance(
                    content_item,
                    dict,
                ):
                    continue

                content_type = str(
                    content_item.get(
                        "type",
                        "",
                    )
                ).strip()

                if content_type == "refusal":
                    refusal = str(
                        content_item.get(
                            "refusal",
                            "",
                        )
                    ).strip()

                    raise CloudVisualAnalyzerError(
                        refusal
                        or (
                            "The visual provider "
                            "refused the request."
                        )
                    )

                text_value = content_item.get(
                    "text"
                )

                if (
                    isinstance(text_value, str)
                    and text_value.strip()
                ):
                    try:
                        return self._parse_json_text(
                            text_value
                        )
                    except CloudVisualAnalyzerError:
                        continue

        raise CloudVisualAnalyzerError(
            "No structured visual observation "
            "was returned by the provider."
        )

    @staticmethod
    def _parse_json_text(
        value: str,
    ) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise CloudVisualAnalyzerError(
                "The visual provider returned "
                "non-JSON output."
            ) from error

        if not isinstance(parsed, dict):
            raise CloudVisualAnalyzerError(
                "The structured visual response "
                "must be a JSON object."
            )

        return parsed

    def _normalize_provider_response(
        self,
        *,
        question: str,
        image_path: str,
        source_uri: str | None,
        provider_json: dict[str, Any],
    ) -> dict[str, Any]:
        entities = self._normalize_entities(
            provider_json.get(
                "entities",
                [],
            )
        )

        relations = self._normalize_relations(
            provider_json.get(
                "relations",
                [],
            )
        )

        return {
            "created_at": (
                datetime.now(
                    UTC
                ).isoformat()
            ),
            "provider": (
                self.config.provider
                .strip()
            ),
            "model": (
                self.config.model
                .strip()
            ),
            "question": question,
            "image_path": image_path,
            "source_uri": (
                source_uri or ""
            ).strip(),
            "scene_description": self._clean_text(
                provider_json.get(
                    "scene_description",
                    "",
                )
            ),
            "visible_text": self._clean_text_list(
                provider_json.get(
                    "visible_text",
                    [],
                )
            ),
            "entities": entities,
            "relations": relations,
            "uncertainties": self._clean_text_list(
                provider_json.get(
                    "uncertainties",
                    [],
                )
            ),
        }

    def _normalize_entities(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        entities: list[
            dict[str, Any]
        ] = []

        for raw_entity in value:
            if not isinstance(
                raw_entity,
                dict,
            ):
                continue

            attributes = (
                self._normalize_attributes(
                    raw_entity.get(
                        "attributes",
                        [],
                    )
                )
            )

            entities.append(
                {
                    "entity_id": self._clean_text(
                        raw_entity.get(
                            "entity_id",
                            "",
                        )
                    ),
                    "label": self._clean_text(
                        raw_entity.get(
                            "label",
                            "",
                        )
                    ),
                    "confidence": (
                        self._normalize_confidence(
                            raw_entity.get(
                                "confidence",
                                0.0,
                            )
                        )
                    ),
                    "attributes": attributes,
                    "states": self._clean_text_list(
                        raw_entity.get(
                            "states",
                            [],
                        )
                    ),
                }
            )

        return entities

    def _normalize_attributes(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        attributes: list[
            dict[str, Any]
        ] = []

        for raw_attribute in value:
            if not isinstance(
                raw_attribute,
                dict,
            ):
                continue

            attributes.append(
                {
                    "name": self._clean_text(
                        raw_attribute.get(
                            "name",
                            "",
                        )
                    ),
                    "value": self._clean_text(
                        raw_attribute.get(
                            "value",
                            "",
                        )
                    ),
                    "confidence": (
                        self._normalize_confidence(
                            raw_attribute.get(
                                "confidence",
                                0.0,
                            )
                        )
                    ),
                }
            )

        return attributes

    def _normalize_relations(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        relations: list[
            dict[str, Any]
        ] = []

        for raw_relation in value:
            if not isinstance(
                raw_relation,
                dict,
            ):
                continue

            relations.append(
                {
                    "relation_id": self._clean_text(
                        raw_relation.get(
                            "relation_id",
                            "",
                        )
                    ),
                    "subject_entity_id": (
                        self._clean_text(
                            raw_relation.get(
                                "subject_entity_id",
                                "",
                            )
                        )
                    ),
                    "predicate": self._clean_text(
                        raw_relation.get(
                            "predicate",
                            "",
                        )
                    ),
                    "object_entity_id": (
                        self._clean_text(
                            raw_relation.get(
                                "object_entity_id",
                                "",
                            )
                        )
                    ),
                    "confidence": (
                        self._normalize_confidence(
                            raw_relation.get(
                                "confidence",
                                0.0,
                            )
                        )
                    ),
                }
            )

        return relations

    @staticmethod
    def _resolve_mime_type(
        image_file: Path,
    ) -> str:
        mime_type = mimetypes.guess_type(
            image_file.name
        )[0]

        supported_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
        }

        if mime_type not in supported_types:
            raise CloudVisualAnalyzerError(
                "Unsupported visual media type: "
                f"{mime_type or 'unknown'}"
            )

        return mime_type

    @staticmethod
    def _normalize_confidence(
        value: Any,
    ) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        return max(
            0.0,
            min(confidence, 1.0),
        )

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(
            value.split()
        ).strip()

    @classmethod
    def _clean_text_list(
        cls,
        value: Any,
    ) -> list[str]:
        if not isinstance(value, list):
            return []

        cleaned: list[str] = []

        for item in value:
            text = cls._clean_text(
                item
            )

            if text:
                cleaned.append(text)

        return cleaned
