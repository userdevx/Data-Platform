from __future__ import annotations

from pathlib import Path

import json
import urllib.error
import urllib.request
from typing import Any

from engine.application.environment import (
    load_project_environment,
)
from services.visual_model.provider_configuration import (
    load_visual_model_registry_configuration,
)
from services.visual_model.provider_contracts import (
    ProcessingLocation,
    VisualCapabilityRequest,
)
from services.visual_model.provider_factory import (
    build_visual_provider_registry,
)


REGISTRY_CONFIGURATION_PATH = Path(
    "config/visual_model/registry.json"
)

CONVERSATION_CAPABILITY = "tool_calling"

DEFAULT_TIMEOUT_SECONDS = 600


class ModelConversationError(RuntimeError):
    """A tool-capable model turn could not be completed."""


def _select_descriptor(
    required_capability: str,
) -> tuple[Any, Any]:
    """
    Choose a provider and model from the registry.

    Mirrors the selection process_automatic_model_request performs:
    the registry names the endpoint, the capability names the model,
    and the policy decides whether local is preferred. Nothing here
    names a host, a port or a model.
    """

    configuration = (
        load_visual_model_registry_configuration(
            REGISTRY_CONFIGURATION_PATH
        )
    )

    policy = configuration.selection_policy

    registry = build_visual_provider_registry(
        configuration
    )

    capability_request = VisualCapabilityRequest(
        required_capabilities=frozenset(
            {required_capability}
        ),
        preferred_processing_location=(
            ProcessingLocation.LOCAL
            if policy.prefer_local
            else None
        ),
        allow_cloud_fallback=(
            policy.allow_cloud_fallback
        ),
        require_structured_output=False,
        maximum_attempts=policy.maximum_attempts,
    )

    candidates = registry.select_models(
        capability_request=capability_request,
        require_runtime_health_check=(
            policy.require_runtime_health_check
        ),
    )

    if not candidates:
        raise ModelConversationError(
            "No registered model declares the "
            + required_capability
            + " capability."
        )

    descriptor = candidates[0]

    for provider in configuration.providers:
        if provider.provider_id != descriptor.provider_id:
            continue

        return provider, descriptor

    raise ModelConversationError(
        "The registry declares no provider for "
        + str(descriptor.provider_id)
    )


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **headers,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as error:
        raise ModelConversationError(
            "The model provider rejected the request. "
            "http_status=" + str(error.code)
        ) from error
    except urllib.error.URLError as error:
        raise ModelConversationError(
            "The model provider could not be reached. "
            "error_type=" + type(error).__name__
        ) from error


def process_model_conversation(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    required_capability: str = CONVERSATION_CAPABILITY,
    max_output_tokens: int = 512,
    context_tokens: int = 8192,
) -> dict[str, Any]:
    """
    One tool-capable model turn.

    Takes the conversation so far and the tools the model may call,
    and returns the provider's message with any tool_calls intact.
    Callers own the loop; this owns provider selection and transport
    so no caller needs to know a host, a port or a model name.
    """

    if not messages:
        raise ValueError("messages is required.")

    load_project_environment()

    provider, descriptor = _select_descriptor(
        required_capability.strip().lower()
        or CONVERSATION_CAPABILITY
    )

    endpoint = str(
        getattr(provider, "endpoint", "")
    ).rstrip("/")

    if not endpoint:
        raise ModelConversationError(
            "The registry declares no endpoint for provider "
            + str(provider.provider_id)
        )

    adapter = str(
        getattr(provider, "adapter_type", "")
    )

    if adapter != "ollama":
        raise ModelConversationError(
            "Tool-calling conversation is not implemented for "
            "adapter type " + adapter
        )

    payload: dict[str, Any] = {
        "model": descriptor.model_id,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "num_ctx": context_tokens,
            "num_predict": max_output_tokens,
        },
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools

    result = _post_json(
        endpoint + "/api/chat",
        payload,
        headers=dict(
            getattr(provider, "headers", {}) or {}
        ),
        timeout_seconds=int(
            getattr(
                provider,
                "timeout_seconds",
                DEFAULT_TIMEOUT_SECONDS,
            )
            or DEFAULT_TIMEOUT_SECONDS
        ),
    )

    message = result.get("message")

    if not isinstance(message, dict):
        raise ModelConversationError(
            "The model provider returned no message."
        )

    return {
        "message": message,
        "provider_id": provider.provider_id,
        "model_id": descriptor.model_id,
        "processing_location": (
            descriptor.processing_location.value
        ),
        "eval_count": result.get("eval_count"),
        "total_duration": result.get("total_duration"),
    }
