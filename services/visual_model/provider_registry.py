from __future__ import annotations

from dataclasses import replace

from services.visual_model.provider_adapter import (
    VisualProviderAdapter,
)
from services.visual_model.provider_contracts import (
    ModelStatus,
    ProcessingLocation,
    VisualCapabilityRequest,
    VisualModelDescriptor,
    VisualProviderRequest,
    VisualProviderResult,
)
from services.visual_model.provider_errors import (
    VisualProviderError,
    VisualProviderRegistrationError,
    VisualProviderUnavailableError,
)


_BLOCKED_STATUSES = {
    ModelStatus.DISABLED,
    ModelStatus.RETIRED,
    ModelStatus.UNAVAILABLE,
    ModelStatus.UNHEALTHY,
    ModelStatus.UNAUTHORIZED,
}


class VisualProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[
            str,
            VisualProviderAdapter,
        ] = {}

    def register(
        self,
        adapter: VisualProviderAdapter,
    ) -> None:
        provider_id = adapter.provider_id.strip()

        if not provider_id:
            raise VisualProviderRegistrationError(
                "The provider identifier is required."
            )

        if provider_id in self._adapters:
            raise VisualProviderRegistrationError(
                "The provider is already registered."
            )

        self._adapters[
            provider_id
        ] = adapter

    def provider_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                self._adapters
            )
        )

    def get(
        self,
        provider_id: str,
    ) -> VisualProviderAdapter:
        try:
            return self._adapters[
                provider_id
            ]
        except KeyError as error:
            raise VisualProviderRegistrationError(
                "The requested provider "
                "is not registered."
            ) from error

    def discover_models(
        self,
    ) -> tuple[VisualModelDescriptor, ...]:
        discovered: list[
            VisualModelDescriptor
        ] = []

        for provider_id in self.provider_ids():
            adapter = self._adapters[
                provider_id
            ]

            discovered.extend(
                adapter.discover_models()
            )

        return tuple(discovered)

    def select_models(
        self,
        *,
        capability_request: (
            VisualCapabilityRequest
        ),
        require_runtime_health_check: bool,
    ) -> tuple[VisualModelDescriptor, ...]:
        candidates: list[
            VisualModelDescriptor
        ] = []

        for descriptor in self.discover_models():
            if not descriptor.enabled:
                continue

            if descriptor.status in _BLOCKED_STATUSES:
                continue

            if (
                not capability_request
                .required_capabilities
                .issubset(
                    descriptor.capabilities
                )
            ):
                continue

            if (
                capability_request
                .require_structured_output
                and not descriptor
                .supports_structured_output
            ):
                continue

            if (
                not capability_request
                .allow_cloud_fallback
                and descriptor
                .processing_location
                is ProcessingLocation.CLOUD
            ):
                continue

            if require_runtime_health_check:
                adapter = self.get(
                    descriptor.provider_id
                )

                health = (
                    adapter.check_model_health(
                        model_id=(
                            descriptor.model_id
                        )
                    )
                )

                descriptor = replace(
                    descriptor,
                    status=health,
                )

                if health is not ModelStatus.AVAILABLE:
                    continue

            candidates.append(descriptor)

        preferred_location = (
            capability_request
            .preferred_processing_location
        )

        def sort_key(
            descriptor: VisualModelDescriptor,
        ) -> tuple[int, int, int, str, str]:
            preferred = (
                preferred_location is not None
                and descriptor.processing_location
                is preferred_location
            )

            local = (
                descriptor.processing_location
                is ProcessingLocation.LOCAL
            )

            private_remote = (
                descriptor.processing_location
                is ProcessingLocation.PRIVATE_REMOTE
            )

            location_rank = (
                0
                if local
                else 1
                if private_remote
                else 2
            )

            return (
                0 if preferred else 1,
                location_rank,
                descriptor.priority,
                descriptor.provider_id,
                descriptor.model_id,
            )

        return tuple(
            sorted(
                candidates,
                key=sort_key,
            )
        )

    def analyze_with_fallback(
        self,
        *,
        capability_request: (
            VisualCapabilityRequest
        ),
        provider_request: VisualProviderRequest,
        require_runtime_health_check: bool,
    ) -> VisualProviderResult:
        candidates = self.select_models(
            capability_request=capability_request,
            require_runtime_health_check=(
                require_runtime_health_check
            ),
        )

        if not candidates:
            raise VisualProviderUnavailableError(
                "No compatible visual model "
                "is currently available."
            )

        maximum_attempts = min(
            capability_request.maximum_attempts,
            len(candidates),
        )

        failures: list[str] = []

        for descriptor in candidates[
            :maximum_attempts
        ]:
            adapter = self.get(
                descriptor.provider_id
            )

            try:
                return adapter.analyze(
                    model_id=descriptor.model_id,
                    request=provider_request,
                )
            except VisualProviderError as error:
                failures.append(
                    f"{descriptor.provider_id}/"
                    f"{descriptor.model_id}: "
                    f"{error}"
                )

        failure_summary = "; ".join(
            failures
        )

        raise VisualProviderUnavailableError(
            "All compatible visual providers "
            "failed."
            + (
                f" {failure_summary}"
                if failure_summary
                else ""
            )
        )
