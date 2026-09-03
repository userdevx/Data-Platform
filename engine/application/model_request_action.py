from __future__ import annotations

from typing import Any
import re

from engine.application.environment import (
    load_project_environment,
)
from services.visual_model.provider_configuration import (
    VisualModelRegistryConfiguration,
    VisualProviderConfiguration,
    load_visual_model_registry_configuration,
)
from services.visual_model.provider_contracts import (
    ModelStatus,
    VisualModelDescriptor,
)
from services.visual_model.provider_errors import (
    VisualProviderResponseError,
    VisualProviderUnavailableError,
)
from services.visual_model.provider_factory import (
    build_visual_provider_registry,
)
from services.visual_model.provider_http import (
    request_json,
    resolve_credential,
)

from engine.application.model_options_action import (
    REGISTRY_CONFIGURATION_PATH,
)

from engine.application.huggingface_model_action import (
    is_hugging_face_provider,
    process_hugging_face_model_request,
)

from engine.application.local_model_action import (
    is_local_model_provider,
    process_local_model_request,
)


def _resolve_requested_capability(
    *,
    descriptor: VisualModelDescriptor,
    requested_capability: str,
) -> str:
    clean_capability = (
        requested_capability
        .strip()
        .lower()
    )

    capabilities = (
        descriptor.capabilities
    )

    if clean_capability:
        if (
            clean_capability
            not in capabilities
        ):
            raise VisualProviderUnavailableError(
                "The selected model does not "
                "support the required capability: "
                f"{clean_capability}"
            )

        return clean_capability

    if "text_input" in capabilities:
        return "text_input"

    if len(capabilities) == 1:
        return next(
            iter(capabilities)
        )

    raise VisualProviderUnavailableError(
        "Select an operation supported "
        "by the selected model."
    )



def _extract_similarity_texts(
    question: str,
) -> tuple[str, str]:
    quoted_values = tuple(
        value.strip()
        for value in re.findall(
            r'["“](.+?)["”]',
            question,
            flags=re.DOTALL,
        )
        if value.strip()
    )

    if len(quoted_values) >= 2:
        return (
            quoted_values[0],
            quoted_values[1],
        )

    blocks = tuple(
        block.strip()
        for block in re.split(
            r"\n\s*\n|\n",
            question,
        )
        if block.strip()
    )

    if len(blocks) >= 2:
        return (
            blocks[-2],
            blocks[-1],
        )

    raise ValueError(
        "The selected model requires two "
        "text values in the same request."
    )


def _build_internal_arguments(
    *,
    question: str,
    capability: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    resolved = dict(arguments)

    if capability != "semantic_similarity":
        return resolved

    has_comparison = bool(
        str(
            resolved.get(
                "comparison_text",
                "",
            )
        ).strip()
    )

    has_comparisons = bool(
        resolved.get(
            "comparison_texts"
        )
    )

    if has_comparison or has_comparisons:
        return resolved

    source_text, comparison_text = (
        _extract_similarity_texts(
            question
        )
    )

    resolved["source_text"] = (
        source_text
    )
    resolved["comparison_text"] = (
        comparison_text
    )

    return resolved


def process_manual_model_request(
    *,
    question: str,
    option_id: str,
    capability: str = "",
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    load_project_environment()

    clean_question = question.strip()
    clean_option_id = option_id.strip()

    if not clean_question:
        raise ValueError(
            "A question is required."
        )

    if not clean_option_id:
        raise ValueError(
            "A model selection is required."
        )

    if clean_option_id == "automatic":
        raise ValueError(
            "Automatic requests must use the "
            "Intelligence Layer."
        )

    if ":" not in clean_option_id:
        raise ValueError(
            "The model option identifier "
            "is invalid."
        )

    provider_id, model_id = (
        clean_option_id.split(
            ":",
            1,
        )
    )

    provider_id = provider_id.strip()
    model_id = model_id.strip()

    if not provider_id or not model_id:
        raise ValueError(
            "The provider and model "
            "identifiers are required."
        )

    if is_local_model_provider(
        provider_id
    ):
        return process_local_model_request(
            question=clean_question,
            model_id=model_id,
            requested_capability=(
                capability
            ),
            arguments=dict(
                arguments or {}
            ),
        )

    configuration = (
        load_visual_model_registry_configuration(
            REGISTRY_CONFIGURATION_PATH
        )
    )

    provider, descriptor = (
        _resolve_selection(
            configuration=configuration,
            provider_id=provider_id,
            model_id=model_id,
        )
    )

    selected_capability = (
        _resolve_requested_capability(
            descriptor=descriptor,
            requested_capability=(
                capability
            ),
        )
    )

    request_arguments = (
        _build_internal_arguments(
            question=clean_question,
            capability=(
                selected_capability
            ),
            arguments=dict(
                arguments or {}
            ),
        )
    )

    results: list[dict[str, Any]] = []

    if provider.adapter_type == "ollama":
        if (
            selected_capability
            != "text_input"
        ):
            raise VisualProviderUnavailableError(
                "The selected model does not "
                "support this operation through "
                "the manual text runtime."
            )

        answer, metadata = _ask_ollama(
            provider=provider,
            model_id=model_id,
            question=clean_question,
        )

    elif (
        provider.adapter_type
        == "openai_responses"
    ):
        if (
            selected_capability
            != "text_input"
        ):
            raise VisualProviderUnavailableError(
                "The selected operation uses "
                "a different application "
                "capability."
            )

        answer, metadata = (
            _ask_openai_responses(
                provider=provider,
                model_id=model_id,
                question=clean_question,
            )
        )

    elif is_hugging_face_provider(
        provider
    ):
        (
            answer,
            metadata,
            results,
        ) = (
            process_hugging_face_model_request(
                provider=provider,
                descriptor=descriptor,
                capability=(
                    selected_capability
                ),
                question=clean_question,
                arguments=request_arguments,
            )
        )

    else:
        raise VisualProviderUnavailableError(
            "The selected provider does not "
            "implement the selected operation."
        )

    return {
        "status": "success",
        "answer": answer,
        "results": results,
        "raw": {
            "status": "success",
            "answer": answer,
            "route": (
                "manual_model_selection"
            ),
            "source": provider.provider_id,
            "capability": (
                selected_capability
            ),
            "provider_id": (
                provider.provider_id
            ),
            "model_id": (
                descriptor.model_id
            ),
            "processing_location": (
                descriptor
                .processing_location
                .value
            ),
            "records_used": [],
            "insights": [],
            "metadata": metadata,
        },
    }


def _resolve_selection(
    *,
    configuration: VisualModelRegistryConfiguration,
    provider_id: str,
    model_id: str,
) -> tuple[
    VisualProviderConfiguration,
    VisualModelDescriptor,
]:
    provider = next(
        (
            item
            for item in configuration.providers
            if item.provider_id == provider_id
        ),
        None,
    )

    if provider is None or not provider.enabled:
        raise VisualProviderUnavailableError(
            "The selected provider is unavailable."
        )

    registry = build_visual_provider_registry(
        configuration
    )

    adapter = registry.get(provider_id)

    discovered_models = adapter.discover_models()

    descriptor = next(
        (
            item
            for item in discovered_models
            if item.model_id == model_id
        ),
        None,
    )

    if descriptor is None:
        raise VisualProviderUnavailableError(
            "The selected model was not returned "
            "by runtime discovery."
        )

    if descriptor.status is not ModelStatus.AVAILABLE:
        raise VisualProviderUnavailableError(
            "The selected model is not currently available."
        )

    return provider, descriptor


def _ask_ollama(
    *,
    provider: VisualProviderConfiguration,
    model_id: str,
    question: str,
) -> tuple[str, dict[str, Any]]:
    response = request_json(
        method="POST",
        url=(
            f"{provider.endpoint}"
            "/api/chat"
        ),
        timeout_seconds=provider.timeout_seconds,
        headers=provider.headers,
        payload={
            "model": model_id,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
            ],
            "options": {
                "num_predict": 1024,
            },
        },
    )

    message = response.get("message")

    if not isinstance(message, dict):
        raise VisualProviderResponseError(
            "The local model response is missing "
            "the message object."
        )

    answer = message.get("content")

    if not isinstance(answer, str) or not answer.strip():
        raise VisualProviderResponseError(
            "The local model returned no answer."
        )

    metadata = {
        "processing_location": "local",
        "done": bool(
            response.get("done", False)
        ),
        "total_duration": response.get(
            "total_duration",
            0,
        ),
        "eval_count": response.get(
            "eval_count",
            0,
        ),
    }

    return answer.strip(), metadata


def _ask_openai_responses(
    *,
    provider: VisualProviderConfiguration,
    model_id: str,
    question: str,
) -> tuple[str, dict[str, Any]]:
    credential = resolve_credential(
        provider.credential_reference
    )

    response = request_json(
        method="POST",
        url=(
            f"{provider.endpoint}"
            f"{provider.analyze_path or '/v1/responses'}"
        ),
        timeout_seconds=provider.timeout_seconds,
        headers={
            **dict(provider.headers),
            "Authorization": (
                f"Bearer {credential}"
            ),
        },
        payload={
            "model": model_id,
            "input": question,
            "max_output_tokens": 1024,
        },
    )

    answer = _extract_openai_output_text(
        response
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

    return answer, {
        "processing_location": "cloud",
        "response_id": response_id,
        "usage": usage,
    }


def _extract_openai_output_text(
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
            "The cloud model response contains "
            "no output."
        )

    text_parts: list[str] = []

    for output_item in output:
        if not isinstance(output_item, dict):
            continue

        content = output_item.get("content")

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
            "The cloud model returned no answer."
        )

    return "\n".join(text_parts)


def process_configured_model_request(
    *,
    question: str,
    provider_name: str,
    model_id: str,
) -> dict[str, Any]:
    """
    Execute a text-model request through the existing provider registry.

    The Intelligence Runtime supplies its configured provider name and
    model. This function resolves that configuration to an enabled
    provider record and delegates to the existing manual-model action.

    No provider endpoint, credential, or provider ID is hardcoded here.
    """

    load_project_environment()

    clean_question = question.strip()
    clean_provider_name = provider_name.strip().lower()
    clean_model_id = model_id.strip()

    if not clean_question:
        raise ValueError(
            "A question is required."
        )

    if not clean_provider_name:
        raise ValueError(
            "A provider name is required."
        )

    if not clean_model_id:
        raise ValueError(
            "A model identifier is required."
        )

    configuration = (
        load_visual_model_registry_configuration(
            REGISTRY_CONFIGURATION_PATH
        )
    )

    matching_providers = []

    for provider in configuration.providers:
        if not provider.enabled:
            continue

        provider_id = (
            provider.provider_id
            .strip()
            .lower()
        )

        adapter_type = (
            provider.adapter_type
            .strip()
            .lower()
        )

        provider_matches = (
            provider_id == clean_provider_name
            or adapter_type == clean_provider_name
            or provider_id.startswith(
                f"{clean_provider_name}-"
            )
            or adapter_type.startswith(
                f"{clean_provider_name}_"
            )
        )

        if not provider_matches:
            continue

        model_available = any(
            model.enabled
            and model.model_id == clean_model_id
            for model in provider.models
        )

        if not model_available:
            continue

        matching_providers.append(
            provider
        )

    if not matching_providers:
        raise VisualProviderUnavailableError(
            "No enabled provider/model combination "
            "matches the active intelligence configuration."
        )

    if len(matching_providers) > 1:
        provider_ids = sorted(
            provider.provider_id
            for provider in matching_providers
        )

        raise VisualProviderUnavailableError(
            "The active provider selection is ambiguous: "
            f"{provider_ids}"
        )

    selected_provider = matching_providers[0]

    return process_manual_model_request(
        question=clean_question,
        option_id=(
            f"{selected_provider.provider_id}:"
            f"{clean_model_id}"
        ),
    )
