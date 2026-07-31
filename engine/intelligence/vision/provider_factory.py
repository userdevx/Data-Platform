from __future__ import annotations

from collections.abc import Callable

from engine.intelligence.vision.analyzer import (
    VisualAnalyzer,
)
from engine.intelligence.vision.config import (
    VisualConfiguration,
)
from engine.intelligence.vision.provider_registry import (
    VisualAnalyzerRegistry,
)
from engine.intelligence.vision.providers.cloud_mapping_adapter import (
    CloudVisualMappingAdapter,
)
from engine.intelligence.vision.providers.cloud_visual_analyzer import (
    CloudVisualAnalyzer,
    CloudVisualAnalyzerConfig,
)
from engine.intelligence.vision.providers.unavailable import (
    UnavailableVisualAnalyzer,
)


REMOTE_VISUAL_PROVIDER_TYPE = "remote_visual"


class VisualProviderConfigurationError(
    ValueError
):
    """Raised when visual provider configuration is invalid."""


VisualAnalyzerBuilder = Callable[
    [VisualConfiguration],
    VisualAnalyzer,
]


def build_remote_visual_analyzer(
    configuration: VisualConfiguration,
) -> VisualAnalyzer:
    runtime = configuration.provider_runtime

    try:
        provider_configuration = (
            CloudVisualAnalyzerConfig(
                provider=configuration.provider,
                model=configuration.model,
                endpoint_url=runtime.endpoint_url,
                api_key_env_var=(
                    runtime
                    .api_key_environment_variable
                ),
                request_timeout_seconds=(
                    runtime
                    .request_timeout_seconds
                ),
                max_output_tokens=(
                    runtime
                    .maximum_output_tokens
                ),
            )
        )
    except ValueError as error:
        raise VisualProviderConfigurationError(
            str(error)
        ) from error

    return CloudVisualMappingAdapter(
        CloudVisualAnalyzer(
            provider_configuration
        )
    )


def build_visual_analyzer_registry(
    configuration: VisualConfiguration,
) -> VisualAnalyzerRegistry:
    registry = VisualAnalyzerRegistry()

    if not configuration.enabled:
        return registry

    provider_name = (
        configuration.provider.strip()
    )

    if not provider_name:
        return registry

    approved_builders: dict[
        str,
        VisualAnalyzerBuilder,
    ] = {
        REMOTE_VISUAL_PROVIDER_TYPE: (
            build_remote_visual_analyzer
        ),
    }

    builder = approved_builders.get(
        provider_name
    )

    if builder is None:
        return registry

    registry.register(
        provider_name=provider_name,
        factory=lambda: builder(
            configuration
        ),
    )

    return registry


def build_visual_analyzer(
    configuration: VisualConfiguration,
) -> VisualAnalyzer:
    if not configuration.enabled:
        return UnavailableVisualAnalyzer()

    registry = build_visual_analyzer_registry(
        configuration
    )

    return registry.create(
        configuration.provider
    )
