from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from engine.intelligence.vision.analyzer import VisualAnalyzer
from engine.intelligence.vision.models import (
    MediaFrame,
    VisualAnalysisRequest,
    VisualObservation,
)
from engine.intelligence.vision.providers.cloud_mapping_adapter import (
    CloudVisualMappingAdapter,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


@dataclass(frozen=True)
class FakeCloudConfiguration:
    provider: str
    model: str


class FakeCloudClient:
    def __init__(
        self,
        result: Any,
        *,
        provider: str = "runtime-provider",
        model: str = "runtime-model",
    ) -> None:
        self.config = FakeCloudConfiguration(
            provider=provider,
            model=model,
        )
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def analyze(
        self,
        *,
        question: str,
        image_path: str,
        source_uri: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "question": question,
                "image_path": image_path,
                "source_uri": source_uri,
            }
        )

        return self.result


def build_request() -> VisualAnalysisRequest:
    return VisualAnalysisRequest(
        request_id=runtime_value("request"),
        query=runtime_value("query"),
        media_source_id=runtime_value("source"),
        media_mode="single_image",
        created_at=datetime.now(UTC).isoformat(),
        source_reference=runtime_value(
            "source-reference"
        ),
    )


def build_frame(
    media_path: Path,
) -> MediaFrame:
    return MediaFrame(
        frame_id=runtime_value("frame"),
        source_id=runtime_value("source"),
        sequence_id=runtime_value("sequence"),
        frame_index=0,
        captured_at=datetime.now(UTC).isoformat(),
        media_location=str(media_path),
        media_type="image/png",
    )


def build_cloud_result() -> dict[str, Any]:
    subject_id = runtime_value("entity")
    object_id = runtime_value("entity")

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "provider": runtime_value("provider"),
        "model": runtime_value("model"),
        "scene_description": runtime_value("scene"),
        "visible_text": [
            runtime_value("visible-text"),
        ],
        "entities": [
            {
                "entity_id": subject_id,
                "label": runtime_value("label"),
                "confidence": 0.91,
                "attributes": [
                    {
                        "name": runtime_value(
                            "attribute"
                        ),
                        "value": runtime_value(
                            "value"
                        ),
                        "confidence": 0.82,
                    }
                ],
                "states": [
                    runtime_value("state"),
                ],
            },
            {
                "entity_id": object_id,
                "label": runtime_value("label"),
                "confidence": 0.74,
                "attributes": [],
                "states": [],
            },
        ],
        "relations": [
            {
                "relation_id": runtime_value(
                    "relation"
                ),
                "subject_entity_id": subject_id,
                "predicate": runtime_value(
                    "predicate"
                ),
                "object_entity_id": object_id,
                "confidence": 0.77,
            }
        ],
        "uncertainties": [
            runtime_value("uncertainty"),
        ],
        "source_uri": runtime_value("source-uri"),
    }


def create_image(
    tmp_path: Path,
) -> Path:
    image_path = tmp_path / "runtime-image.png"
    image_path.write_bytes(
        b"runtime-image-data"
    )
    return image_path


def test_adapter_satisfies_visual_analyzer_protocol() -> None:
    adapter = CloudVisualMappingAdapter(
        FakeCloudClient(
            build_cloud_result()
        )
    )

    assert isinstance(
        adapter,
        VisualAnalyzer,
    )


def test_adapter_calls_cloud_client_with_request_values(
    tmp_path: Path,
) -> None:
    request = build_request()
    frame = build_frame(
        create_image(tmp_path)
    )
    client = FakeCloudClient(
        build_cloud_result()
    )

    adapter = CloudVisualMappingAdapter(
        client
    )

    adapter.analyze(
        request=request,
        frame=frame,
    )

    assert client.calls == [
        {
            "question": request.query,
            "image_path": frame.media_location,
            "source_uri": request.source_reference,
        }
    ]


def test_adapter_returns_visual_observation(
    tmp_path: Path,
) -> None:
    request = build_request()
    frame = build_frame(
        create_image(tmp_path)
    )
    result = build_cloud_result()

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    ).analyze(
        request=request,
        frame=frame,
    )

    assert isinstance(
        observation,
        VisualObservation,
    )
    assert observation.observation_id
    assert observation.request_id == request.request_id
    assert observation.frame_id == frame.frame_id
    assert observation.sequence_id == frame.sequence_id
    assert observation.query == request.query
    assert (
        observation.scene_description
        == result["scene_description"]
    )


def test_adapter_preserves_explicit_observation_id(
    tmp_path: Path,
) -> None:
    result = build_cloud_result()
    observation_id = runtime_value(
        "observation"
    )
    result["observation_id"] = observation_id

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    ).analyze(
        request=build_request(),
        frame=build_frame(
            create_image(tmp_path)
        ),
    )

    assert (
        observation.observation_id
        == observation_id
    )


def test_adapter_maps_entities_and_attributes(
    tmp_path: Path,
) -> None:
    result = build_cloud_result()

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    ).analyze(
        request=build_request(),
        frame=build_frame(
            create_image(tmp_path)
        ),
    )

    source_entity = result["entities"][0]
    source_attribute = source_entity[
        "attributes"
    ][0]
    entity = observation.entities[0]

    assert entity.entity_id == (
        source_entity["entity_id"]
    )
    assert entity.label == (
        source_entity["label"]
    )
    assert entity.confidence == (
        source_entity["confidence"]
    )
    assert entity.attributes[
        source_attribute["name"]
    ] == {
        "value": source_attribute["value"],
        "confidence": (
            source_attribute["confidence"]
        ),
    }
    assert entity.attributes["states"] == (
        source_entity["states"]
    )


def test_adapter_maps_relations(
    tmp_path: Path,
) -> None:
    result = build_cloud_result()

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    ).analyze(
        request=build_request(),
        frame=build_frame(
            create_image(tmp_path)
        ),
    )

    source_relation = result["relations"][0]
    relation = observation.relations[0]

    assert relation.subject_id == (
        source_relation[
            "subject_entity_id"
        ]
    )
    assert relation.predicate == (
        source_relation["predicate"]
    )
    assert relation.object_id == (
        source_relation[
            "object_entity_id"
        ]
    )
    assert relation.attributes[
        "relation_id"
    ] == source_relation[
        "relation_id"
    ]


def test_adapter_maps_visible_text_and_uncertainty(
    tmp_path: Path,
) -> None:
    result = build_cloud_result()

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    ).analyze(
        request=build_request(),
        frame=build_frame(
            create_image(tmp_path)
        ),
    )

    assert observation.visible_text == tuple(
        result["visible_text"]
    )
    assert observation.uncertainty == tuple(
        result["uncertainties"]
    )


def test_adapter_preserves_configured_provider_identity(
    tmp_path: Path,
) -> None:
    provider = runtime_value("provider")
    model = runtime_value("model")

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(
            build_cloud_result(),
            provider=provider,
            model=model,
        )
    ).analyze(
        request=build_request(),
        frame=build_frame(
            create_image(tmp_path)
        ),
    )

    assert observation.provider_name == provider
    assert observation.provider_model == model


def test_adapter_rejects_missing_provider() -> None:
    with pytest.raises(
        ValueError,
        match="provider",
    ):
        CloudVisualMappingAdapter(
            FakeCloudClient(
                build_cloud_result(),
                provider="",
            )
        )


def test_adapter_rejects_missing_model() -> None:
    with pytest.raises(
        ValueError,
        match="model",
    ):
        CloudVisualMappingAdapter(
            FakeCloudClient(
                build_cloud_result(),
                model="",
            )
        )


def test_adapter_rejects_non_mapping_response(
    tmp_path: Path,
) -> None:
    adapter = CloudVisualMappingAdapter(
        FakeCloudClient([])
    )

    with pytest.raises(
        ValueError,
        match="must be an object",
    ):
        adapter.analyze(
            request=build_request(),
            frame=build_frame(
                create_image(tmp_path)
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        (
            "entities",
            {},
            "entities must be a list",
        ),
        (
            "relations",
            {},
            "relations must be a list",
        ),
    ],
)
def test_adapter_rejects_invalid_collections(
    field_name: str,
    invalid_value: Any,
    message: str,
    tmp_path: Path,
) -> None:
    result = build_cloud_result()
    result[field_name] = invalid_value

    adapter = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        adapter.analyze(
            request=build_request(),
            frame=build_frame(
                create_image(tmp_path)
            ),
        )


def test_adapter_clamps_confidence_values(
    tmp_path: Path,
) -> None:
    result = build_cloud_result()
    result["entities"][0][
        "confidence"
    ] = 4
    result["relations"][0][
        "confidence"
    ] = -2

    observation = CloudVisualMappingAdapter(
        FakeCloudClient(result)
    ).analyze(
        request=build_request(),
        frame=build_frame(
            create_image(tmp_path)
        ),
    )

    assert (
        observation.entities[0].confidence
        == 1.0
    )
    assert (
        observation.relations[0].confidence
        == 0.0
    )
