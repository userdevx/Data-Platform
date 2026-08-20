from services.visual_model.provider_configuration import (
    VisualModelRegistryConfiguration,
)
from services.visual_model.provider_errors import (
    VisualProviderConfigurationError,
)
from services.visual_model.provider_registry import (
    VisualProviderRegistry,
)
from services.visual_model.providers.huggingface_inference_adapter import (
    HuggingFaceInferenceProvider,
)
from services.visual_model.providers.ollama_visual_adapter import (
    OllamaVisualProvider,
)
from services.visual_model.providers.openai_responses_adapter import (
    OpenAIResponsesVisualProvider,
)
from services.visual_model.providers.remote_json_adapter import (
    RemoteJsonVisualProvider,
)


OLLAMA_ADAPTER_TYPE = "ollama"

OPENAI_RESPONSES_ADAPTER_TYPE = (
    "openai_responses"
)

REMOTE_JSON_ADAPTER_TYPE = "remote_json"

HUGGINGFACE_INFERENCE_ADAPTER_TYPE = (
    "huggingface_inference"
)


def build_visual_provider_registry(
    configuration: VisualModelRegistryConfiguration,
) -> VisualProviderRegistry:
    registry = VisualProviderRegistry()

    if not configuration.enabled:
        return registry

    for provider in configuration.providers:
        if not provider.enabled:
            continue

        if (
            provider.adapter_type
            == OLLAMA_ADAPTER_TYPE
        ):
            adapter = OllamaVisualProvider(
                provider
            )

        elif (
            provider.adapter_type
            == OPENAI_RESPONSES_ADAPTER_TYPE
        ):
            adapter = (
                OpenAIResponsesVisualProvider(
                    provider
                )
            )

        elif (
            provider.adapter_type
            == REMOTE_JSON_ADAPTER_TYPE
        ):
            adapter = RemoteJsonVisualProvider(
                provider
            )

        elif (
            provider.adapter_type
            == HUGGINGFACE_INFERENCE_ADAPTER_TYPE
        ):
            adapter = (
                HuggingFaceInferenceProvider(
                    provider
                )
            )

        else:
            raise VisualProviderConfigurationError(
                "Unsupported visual provider "
                "adapter type: "
                f"{provider.adapter_type}"
            )

        registry.register(adapter)

    return registry
