from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from engine.intelligence.vision.models import (
    MediaFrame,
    VisualAnalysisRequest,
    VisualEntity,
    VisualObservation,
    VisualRelation,
)


ProviderCall = Callable[
    [VisualAnalysisRequest, MediaFrame],
    dict[str, Any],
]


class MappingVisualAnalyzer:
    def __init__(
        self,
        *,
        provider_name: str,
        provider_model: str,
        provider_call: ProviderCall,
    ) -> None:
        self.provider_name = provider_name.strip()
        self.provider_model = provider_model.strip()
        self.provider_call = provider_call

        if not self.provider_name:
            raise ValueError(
                "provider_name is required."
            )

        if not self.provider_model:
            raise ValueError(
                "provider_model is required."
            )

    def analyze(
        self,
        *,
        request: VisualAnalysisRequest,
        frame: MediaFrame,
    ) -> VisualObservation:
        payload = self.provider_call(
            request,
            frame,
        )

        if not isinstance(payload, dict):
            raise ValueError(
                "The provider response must be an object."
            )

        raw_entities = payload.get(
            "entities",
            [],
        )
        raw_relations = payload.get(
            "relations",
            [],
        )

        if not isinstance(raw_entities, list):
            raise ValueError(
                "entities must be a list."
            )

        if not isinstance(raw_relations, list):
            raise ValueError(
                "relations must be a list."
            )

        entities = tuple(
            self._entity_from_mapping(item)
            for item in raw_entities
            if isinstance(item, dict)
        )

        relations = tuple(
            self._relation_from_mapping(item)
            for item in raw_relations
            if isinstance(item, dict)
        )

        visible_text = self._string_tuple(
            payload.get("visible_text", [])
        )
        uncertainty = self._string_tuple(
            payload.get("uncertainty", [])
        )

        return VisualObservation(
            observation_id=str(
                payload.get(
                    "observation_id",
                    uuid4().hex,
                )
            ).strip(),
            request_id=request.request_id,
            frame_id=frame.frame_id,
            sequence_id=frame.sequence_id,
            frame_index=frame.frame_index,
            captured_at=frame.captured_at,
            query=request.query,
            scene_description=str(
                payload.get(
                    "scene_description",
                    "",
                )
            ).strip(),
            entities=entities,
            relations=relations,
            visible_text=visible_text,
            uncertainty=uncertainty,
            provider_name=self.provider_name,
            provider_model=self.provider_model,
            source_reference=request.source_reference,
            metadata={
                "provider_metadata": payload.get(
                    "metadata",
                    {},
                ),
            },
        )

    @staticmethod
    def _entity_from_mapping(
        value: dict[str, Any],
    ) -> VisualEntity:
        attributes = value.get(
            "attributes",
            {},
        )

        if not isinstance(attributes, dict):
            attributes = {}

        return VisualEntity(
            entity_id=str(
                value.get(
                    "entity_id",
                    uuid4().hex,
                )
            ).strip(),
            label=str(
                value.get("label", "")
            ).strip(),
            confidence=float(
                value.get("confidence", 0.0)
            ),
            attributes=dict(attributes),
        )

    @staticmethod
    def _relation_from_mapping(
        value: dict[str, Any],
    ) -> VisualRelation:
        attributes = value.get(
            "attributes",
            {},
        )

        if not isinstance(attributes, dict):
            attributes = {}

        object_value = value.get("object_id")

        return VisualRelation(
            subject_id=str(
                value.get("subject_id", "")
            ).strip(),
            predicate=str(
                value.get("predicate", "")
            ).strip(),
            object_id=(
                str(object_value).strip()
                if object_value is not None
                else None
            ),
            confidence=float(
                value.get("confidence", 0.0)
            ),
            attributes=dict(attributes),
        )

    @staticmethod
    def _string_tuple(
        value: Any,
    ) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()

        return tuple(
            text
            for item in value
            if (text := str(item).strip())
        )
