from __future__ import annotations

import os
from dataclasses import replace

from huggingface_hub import HfApi, InferenceClient

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
    VisualProviderUnavailableError,
)
from services.visual_model.provider_http import (
    resolve_credential,
)


MODEL_ID_ENVIRONMENT_KEY = "model_id_environment"


class HuggingFaceInferenceProvider:
    """
    Hugging Face provider for explicitly configured
    specialized capabilities.
    """

    def __init__(
        self,
        configuration: VisualProviderConfiguration,
    ) -> None:
        self._configuration = configuration

    @property
    def provider_id(self) -> str:
        return self._configuration.provider_id

    def _credential(self) -> str:
        try:
            return resolve_credential(
                self._configuration.credential_reference
            )
        except Exception as error:
            raise VisualProviderUnavailableError(
                "The Hugging Face credential is unavailable."
            ) from error

    @staticmethod
    def _resolve_configured_model_id(
        descriptor: VisualModelDescriptor,
    ) -> str:
        environment_name = str(
            descriptor.metadata.get(
                MODEL_ID_ENVIRONMENT_KEY,
                "",
            )
        ).strip()

        if not environment_name:
            return descriptor.model_id

        model_id = os.getenv(
            environment_name,
            "",
        ).strip()

        if not model_id:
            raise VisualProviderUnavailableError(
                f"{environment_name} is required."
            )

        return model_id

    def discover_models(
        self,
    ) -> tuple[VisualModelDescriptor, ...]:
        if not self._configuration.enabled:
            return ()

        discovered_models: list[
            VisualModelDescriptor
        ] = []

        for descriptor in self._configuration.models:
            if not descriptor.enabled:
                discovered_models.append(
                    replace(
                        descriptor,
                        status=ModelStatus.DISABLED,
                    )
                )
                continue

            try:
                model_id = (
                    self._resolve_configured_model_id(
                        descriptor
                    )
                )
            except VisualProviderUnavailableError:
                discovered_models.append(
                    replace(
                        descriptor,
                        status=ModelStatus.UNAVAILABLE,
                    )
                )
                continue

            discovered_models.append(
                replace(
                    descriptor,
                    model_id=model_id,
                    status=self.check_model_health(
                        model_id=model_id
                    ),
                )
            )

        return tuple(discovered_models)

    def check_model_health(
        self,
        *,
        model_id: str,
    ) -> ModelStatus:
        if not self._configuration.enabled:
            return ModelStatus.DISABLED

        clean_model_id = model_id.strip()

        if not clean_model_id:
            return ModelStatus.UNAVAILABLE

        try:
            credential = self._credential()
        except VisualProviderUnavailableError:
            return ModelStatus.UNAUTHORIZED

        try:
            api = HfApi(
                endpoint=self._configuration.endpoint,
                token=credential,
            )

            information = api.model_info(
                clean_model_id,
                timeout=float(
                    self._configuration.timeout_seconds
                ),
            )
        except Exception:
            return ModelStatus.UNHEALTHY

        if bool(
            getattr(
                information,
                "disabled",
                False,
            )
        ):
            return ModelStatus.UNAVAILABLE

        return ModelStatus.AVAILABLE

    def sentence_similarity(
        self,
        *,
        model_id: str,
        source_text: str,
        candidate_texts: tuple[str, ...],
    ) -> tuple[float, ...]:
        clean_model_id = model_id.strip()
        clean_source_text = source_text.strip()

        clean_candidate_texts = tuple(
            candidate.strip()
            for candidate in candidate_texts
            if candidate.strip()
        )

        if not clean_model_id:
            raise ValueError(
                "A Hugging Face model ID is required."
            )

        if not clean_source_text:
            raise ValueError(
                "Source text is required."
            )

        if not clean_candidate_texts:
            raise ValueError(
                "At least one candidate text is required."
            )

        credential = self._credential()

        client = InferenceClient(
            provider="hf-inference",
            api_key=credential,
            timeout=float(
                self._configuration.timeout_seconds
            ),
        )

        try:
            result = client.sentence_similarity(
                clean_source_text,
                other_sentences=list(
                    clean_candidate_texts
                ),
                model=clean_model_id,
            )
        except Exception as error:
            raise VisualProviderUnavailableError(
                "The Hugging Face sentence-similarity "
                "request could not be completed."
            ) from error

        if not isinstance(result, list):
            raise VisualProviderResponseError(
                "The Hugging Face provider returned "
                "an invalid similarity result."
            )

        if len(result) != len(
            clean_candidate_texts
        ):
            raise VisualProviderResponseError(
                "The Hugging Face provider returned "
                "an unexpected number of scores."
            )

        try:
            return tuple(
                float(score)
                for score in result
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise VisualProviderResponseError(
                "The Hugging Face provider returned "
                "an invalid similarity score."
            ) from error

    def analyze(
        self,
        *,
        model_id: str,
        request: VisualProviderRequest,
    ) -> VisualProviderResult:
        del model_id
        del request

        raise VisualProviderUnavailableError(
            "This Hugging Face provider is configured "
            "for specialized text capabilities, not "
            "visual analysis."
        )
