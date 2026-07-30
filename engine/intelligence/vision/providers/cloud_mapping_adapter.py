from __future__ import annotations

from typing import Any, Protocol

from engine.intelligence.vision.models import (
    MediaFrame,
    VisualAnalysisRequest,
    VisualObservation,
)
from engine.intelligence.vision.providers.mapping_adapter import (
    MappingVisualAnalyzer,
)


class CloudVisualClientConfiguration(Protocol):
    provider: str
    model: str


class CloudVisualClient(Protocol):
    config: CloudVisualClientConfiguration

    def analyze(
        self,
        *,
        question: str,
        image_path: str,
        source_uri: str | None = None,
    ) -> dict[str, Any]:
        ...


class CloudVisualMappingAdapter:
    """
    Adapts a cloud visual client to the existing VisualAnalyzer contract.

    The cloud client handles provider-specific transport and normalization.
    This adapter converts that normalized mapping into the field structure
    already accepted by MappingVisualAnalyzer.
    """

    def __init__(
        self,
        cloud_client: CloudVisualClient,
    ) -> None:
        self.cloud_client = cloud_client

        provider_name = self._configuration_text(
            "provider"
        )
        provider_model = self._configuration_text(
            "model"
        )

        self._mapping_analyzer = MappingVisualAnalyzer(
            provider_name=provider_name,
            provider_model=provider_model,
            provider_call=self._provider_call,
        )

    def analyze(
        self,
        *,
        request: VisualAnalysisRequest,
        frame: MediaFrame,
    ) -> VisualObservation:
        return self._mapping_analyzer.analyze(
            request=request,
            frame=frame,
        )

    def _provider_call(
        self,
        request: VisualAnalysisRequest,
        frame: MediaFrame,
    ) -> dict[str, Any]:
        cloud_result = self.cloud_client.analyze(
            question=request.query,
            image_path=frame.media_location,
            source_uri=request.source_reference,
        )

        if not isinstance(cloud_result, dict):
            raise ValueError(
                "The cloud visual provider response "
                "must be an object."
            )

        return self._map_cloud_result(
            cloud_result
        )

    def _map_cloud_result(
        self,
        cloud_result: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scene_description": self._clean_text(
                cloud_result.get(
                    "scene_description",
                    "",
                )
            ),
            "visible_text": self._clean_text_list(
                cloud_result.get(
                    "visible_text",
                    [],
                )
            ),
            "uncertainty": self._clean_text_list(
                cloud_result.get(
                    "uncertainties",
                    cloud_result.get(
                        "uncertainty",
                        [],
                    ),
                )
            ),
            "entities": self._map_entities(
                cloud_result.get(
                    "entities",
                    [],
                )
            ),
            "relations": self._map_relations(
                cloud_result.get(
                    "relations",
                    [],
                )
            ),
            "metadata": {
                "cloud_provider": self._clean_text(
                    cloud_result.get(
                        "provider",
                        self._configuration_text(
                            "provider"
                        ),
                    )
                ),
                "cloud_model": self._clean_text(
                    cloud_result.get(
                        "model",
                        self._configuration_text(
                            "model"
                        ),
                    )
                ),
                "cloud_created_at": self._clean_text(
                    cloud_result.get(
                        "created_at",
                        "",
                    )
                ),
                "source_uri": self._clean_text(
                    cloud_result.get(
                        "source_uri",
                        "",
                    )
                ),
            },
        }

        observation_id = self._clean_text(
            cloud_result.get(
                "observation_id",
                "",
            )
        )

        if observation_id:
            payload["observation_id"] = (
                observation_id
            )

        return payload

    def _map_entities(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(
                "Cloud visual entities must be a list."
            )

        entities: list[dict[str, Any]] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            attributes = self._map_attributes(
                item.get(
                    "attributes",
                    [],
                )
            )

            states = self._clean_text_list(
                item.get(
                    "states",
                    [],
                )
            )

            if states:
                attributes["states"] = states

            entities.append(
                {
                    "entity_id": self._clean_text(
                        item.get(
                            "entity_id",
                            "",
                        )
                    ),
                    "label": self._clean_text(
                        item.get(
                            "label",
                            "",
                        )
                    ),
                    "confidence": self._confidence(
                        item.get(
                            "confidence",
                            0.0,
                        )
                    ),
                    "attributes": attributes,
                }
            )

        return entities

    def _map_attributes(
        self,
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)

        if not isinstance(value, list):
            return {}

        attributes: dict[str, Any] = {}

        for item in value:
            if not isinstance(item, dict):
                continue

            name = self._clean_text(
                item.get(
                    "name",
                    "",
                )
            )

            if not name:
                continue

            attributes[name] = {
                "value": self._clean_text(
                    item.get(
                        "value",
                        "",
                    )
                ),
                "confidence": self._confidence(
                    item.get(
                        "confidence",
                        0.0,
                    )
                ),
            }

        return attributes

    def _map_relations(
        self,
        value: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(
                "Cloud visual relations must be a list."
            )

        relations: list[dict[str, Any]] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            relation_id = self._clean_text(
                item.get(
                    "relation_id",
                    "",
                )
            )

            relation_attributes: dict[str, Any] = {}

            if relation_id:
                relation_attributes[
                    "relation_id"
                ] = relation_id

            relations.append(
                {
                    "subject_id": self._clean_text(
                        item.get(
                            "subject_entity_id",
                            item.get(
                                "subject_id",
                                "",
                            ),
                        )
                    ),
                    "predicate": self._clean_text(
                        item.get(
                            "predicate",
                            "",
                        )
                    ),
                    "object_id": self._optional_text(
                        item.get(
                            "object_entity_id",
                            item.get(
                                "object_id",
                            ),
                        )
                    ),
                    "confidence": self._confidence(
                        item.get(
                            "confidence",
                            0.0,
                        )
                    ),
                    "attributes": relation_attributes,
                }
            )

        return relations

    def _configuration_text(
        self,
        field_name: str,
    ) -> str:
        configuration = getattr(
            self.cloud_client,
            "config",
            None,
        )

        value = getattr(
            configuration,
            field_name,
            "",
        )

        clean_value = self._clean_text(
            value
        )

        if not clean_value:
            raise ValueError(
                f"Cloud visual {field_name} "
                "configuration is required."
            )

        return clean_value

    @staticmethod
    def _confidence(
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

    @classmethod
    def _optional_text(
        cls,
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        cleaned = cls._clean_text(
            value
        )

        return cleaned or None
