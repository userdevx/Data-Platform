from __future__ import annotations

from typing import Any

from engine.application.environment import (
    load_project_environment,
)
from engine.application.model_options_action import (
    REGISTRY_CONFIGURATION_PATH,
)
from engine.application.model_request_action import (
    process_manual_model_request,
)
from services.visual_model.provider_configuration import (
    load_visual_model_registry_configuration,
)
from services.visual_model.provider_contracts import (
    ProcessingLocation,
    VisualCapabilityRequest,
)
from services.visual_model.provider_errors import (
    VisualProviderError,
    VisualProviderUnavailableError,
)
from services.visual_model.provider_factory import (
    build_visual_provider_registry,
)


def _validate_request_arguments(
    *,
    required_capability: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    clean_arguments = dict(
        arguments or {}
    )

    if (
        required_capability
        == "semantic_similarity"
    ):
        comparison_text = str(
            clean_arguments.get(
                "comparison_text",
                "",
            )
        ).strip()

        comparison_texts = (
            clean_arguments.get(
                "comparison_texts"
            )
        )

        has_multiple = (
            isinstance(
                comparison_texts,
                list,
            )
            and any(
                str(item).strip()
                for item
                in comparison_texts
            )
        )

        if (
            not comparison_text
            and not has_multiple
        ):
            raise ValueError(
                "semantic_similarity requires "
                "comparison_text or "
                "comparison_texts."
            )

    return clean_arguments


def process_automatic_model_request(
    *,
    question: str,
    required_capability: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    load_project_environment()

    clean_question = question.strip()

    clean_capability = (
        required_capability
        .strip()
        .lower()
    )

    if not clean_question:
        raise ValueError(
            "A question is required."
        )

    if not clean_capability:
        raise ValueError(
            "A required capability "
            "is required."
        )

    request_arguments = (
        _validate_request_arguments(
            required_capability=(
                clean_capability
            ),
            arguments=arguments,
        )
    )

    configuration = (
        load_visual_model_registry_configuration(
            REGISTRY_CONFIGURATION_PATH
        )
    )

    policy = (
        configuration.selection_policy
    )

    registry = (
        build_visual_provider_registry(
            configuration
        )
    )

    preferred_location = (
        ProcessingLocation.LOCAL
        if policy.prefer_local
        else None
    )

    capability_request = (
        VisualCapabilityRequest(
            required_capabilities=(
                frozenset(
                    {
                        clean_capability
                    }
                )
            ),
            preferred_processing_location=(
                preferred_location
            ),
            allow_cloud_fallback=(
                policy
                .allow_cloud_fallback
            ),
            require_structured_output=False,
            maximum_attempts=(
                policy.maximum_attempts
            ),
        )
    )

    candidates = registry.select_models(
        capability_request=(
            capability_request
        ),
        require_runtime_health_check=(
            policy
            .require_runtime_health_check
        ),
    )

    if not candidates:
        raise VisualProviderUnavailableError(
            "No available model supports "
            "the required capability: "
            f"{clean_capability}"
        )

    maximum_attempts = min(
        policy.maximum_attempts,
        len(candidates),
    )

    failures: list[str] = []

    for descriptor in candidates[
        :maximum_attempts
    ]:
        option_id = (
            f"{descriptor.provider_id}:"
            f"{descriptor.model_id}"
        )

        try:
            result = (
                process_manual_model_request(
                    question=clean_question,
                    option_id=option_id,
                    capability=(
                        clean_capability
                    ),
                    arguments=request_arguments,
                )
            )

            raw = result.get(
                "raw",
                {},
            )

            if isinstance(raw, dict):
                raw[
                    "route"
                ] = (
                    "automatic_model_selection"
                )

                raw[
                    "selection"
                ] = {
                    "required_capability": (
                        clean_capability
                    ),
                    "candidate_count": (
                        len(candidates)
                    ),
                    "selected_provider_id": (
                        descriptor.provider_id
                    ),
                    "selected_model_id": (
                        descriptor.model_id
                    ),
                    "processing_location": (
                        descriptor
                        .processing_location
                        .value
                    ),
                }

            return result

        except (
            OSError,
            ValueError,
            VisualProviderError,
        ) as error:
            failures.append(
                f"{descriptor.provider_id}/"
                f"{descriptor.model_id}: "
                f"{error}"
            )

    raise VisualProviderUnavailableError(
        "Compatible models were found, "
        "but none completed the request. "
        + "; ".join(failures)
    )
