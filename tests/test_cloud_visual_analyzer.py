from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from engine.intelligence.vision.providers.cloud_visual_analyzer import (
    CloudVisualAnalyzer,
    CloudVisualAnalyzerConfig,
    CloudVisualAnalyzerError,
)


def runtime_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def build_configuration(
    *,
    provider: str = "openai",
    model: str | None = None,
    endpoint_url: str | None = None,
    api_key_env_var: str | None = None,
    request_timeout_seconds: int = 60,
    max_output_tokens: int = 1200,
) -> CloudVisualAnalyzerConfig:
    return CloudVisualAnalyzerConfig(
        provider=provider,
        model=model or runtime_value("model"),
        endpoint_url=(
            endpoint_url
            or "https://example.invalid/v1/responses"
        ),
        api_key_env_var=(
            api_key_env_var
            or runtime_value("VISUAL_API_KEY").upper()
        ),
        request_timeout_seconds=request_timeout_seconds,
        max_output_tokens=max_output_tokens,
    )


def build_provider_observation() -> dict[str, Any]:
    subject_id = runtime_value("entity")
    object_id = runtime_value("entity")

    return {
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
                        "name": runtime_value("attribute"),
                        "value": runtime_value("value"),
                        "confidence": 0.84,
                    }
                ],
                "states": [
                    runtime_value("state"),
                ],
            },
            {
                "entity_id": object_id,
                "label": runtime_value("label"),
                "confidence": 0.79,
                "attributes": [],
                "states": [],
            },
        ],
        "relations": [
            {
                "relation_id": runtime_value("relation"),
                "subject_entity_id": subject_id,
                "predicate": runtime_value("predicate"),
                "object_entity_id": object_id,
                "confidence": 0.76,
            }
        ],
        "uncertainties": [
            runtime_value("uncertainty"),
        ],
    }


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
        "expected_message",
    ),
    [
        ("provider", "", "provider"),
        ("model", "", "model"),
        ("endpoint_url", "", "endpoint"),
        (
            "api_key_env_var",
            "",
            "environment-variable",
        ),
    ],
)
def test_configuration_rejects_missing_values(
    field_name: str,
    field_value: str,
    expected_message: str,
) -> None:
    values: dict[str, Any] = {
        "provider": "openai",
        "model": runtime_value("model"),
        "endpoint_url": (
            "https://example.invalid/v1/responses"
        ),
        "api_key_env_var": runtime_value(
            "VISUAL_API_KEY"
        ).upper(),
        "request_timeout_seconds": 60,
        "max_output_tokens": 1200,
    }

    values[field_name] = field_value

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        CloudVisualAnalyzerConfig(**values)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("request_timeout_seconds", 0),
        ("request_timeout_seconds", -1),
        ("max_output_tokens", 0),
        ("max_output_tokens", -1),
    ],
)
def test_configuration_rejects_nonpositive_limits(
    field_name: str,
    field_value: int,
) -> None:
    values: dict[str, Any] = {
        "provider": "openai",
        "model": runtime_value("model"),
        "endpoint_url": (
            "https://example.invalid/v1/responses"
        ),
        "api_key_env_var": runtime_value(
            "VISUAL_API_KEY"
        ).upper(),
        "request_timeout_seconds": 60,
        "max_output_tokens": 1200,
    }

    values[field_name] = field_value

    with pytest.raises(
        ValueError,
        match="positive",
    ):
        CloudVisualAnalyzerConfig(**values)


def test_analyze_rejects_empty_question(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()

    monkeypatch.setenv(
        configuration.api_key_env_var,
        runtime_value("key"),
    )

    image_path = tmp_path / "media.png"
    image_path.write_bytes(b"runtime-media")

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="question",
    ):
        analyzer.analyze(
            question=" ",
            image_path=str(image_path),
        )


def test_analyze_rejects_missing_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()

    monkeypatch.delenv(
        configuration.api_key_env_var,
        raising=False,
    )

    image_path = tmp_path / "media.png"
    image_path.write_bytes(b"runtime-media")

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="API key",
    ):
        analyzer.analyze(
            question=runtime_value("question"),
            image_path=str(image_path),
        )


def test_analyze_rejects_missing_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()

    monkeypatch.setenv(
        configuration.api_key_env_var,
        runtime_value("key"),
    )

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="not found",
    ):
        analyzer.analyze(
            question=runtime_value("question"),
            image_path=str(
                tmp_path / "missing.png"
            ),
        )


def test_analyze_rejects_unsupported_media_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()

    monkeypatch.setenv(
        configuration.api_key_env_var,
        runtime_value("key"),
    )

    media_path = tmp_path / "media.data"
    media_path.write_bytes(b"runtime-media")

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="Unsupported visual media type",
    ):
        analyzer.analyze(
            question=runtime_value("question"),
            image_path=str(media_path),
        )


@pytest.mark.parametrize(
    "suffix",
    [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
    ],
)
def test_supported_media_types_are_accepted(
    suffix: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()

    monkeypatch.setenv(
        configuration.api_key_env_var,
        runtime_value("key"),
    )

    media_path = tmp_path / f"media{suffix}"
    media_path.write_bytes(b"runtime-media")

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    monkeypatch.setattr(
        analyzer,
        "_post_json",
        lambda **_: {
            "output_text": json.dumps(
                build_provider_observation()
            )
        },
    )

    result = analyzer.analyze(
        question=runtime_value("question"),
        image_path=str(media_path),
    )

    assert result["entities"]


def test_payload_contains_local_base64_image() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    encoded_image = runtime_value(
        "encoded-media"
    )

    payload = analyzer._build_payload(
        question=runtime_value("question"),
        encoded_image=encoded_image,
        mime_type="image/png",
    )

    user_content = payload["input"][1][
        "content"
    ]

    image_input = next(
        item
        for item in user_content
        if item["type"] == "input_image"
    )

    assert image_input["image_url"] == (
        "data:image/png;base64,"
        f"{encoded_image}"
    )


def test_payload_uses_configured_model() -> None:
    configured_model = runtime_value("model")

    analyzer = CloudVisualAnalyzer(
        build_configuration(
            model=configured_model,
        )
    )

    payload = analyzer._build_payload(
        question=runtime_value("question"),
        encoded_image=runtime_value("media"),
        mime_type="image/png",
    )

    assert payload["model"] == configured_model


def test_payload_uses_strict_generic_schema() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    payload = analyzer._build_payload(
        question=runtime_value("question"),
        encoded_image=runtime_value("media"),
        mime_type="image/png",
    )

    response_format = payload["text"][
        "format"
    ]

    schema = response_format["schema"]

    assert response_format["strict"] is True

    assert set(schema["required"]) == {
        "scene_description",
        "visible_text",
        "entities",
        "relations",
        "uncertainties",
    }

    assert not contains_enum(schema)


def test_payload_rejects_unsupported_provider() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration(
            provider=runtime_value("provider"),
        )
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="Unsupported",
    ):
        analyzer._build_payload(
            question=runtime_value("question"),
            encoded_image=runtime_value("media"),
            mime_type="image/png",
        )


def test_extracts_top_level_output_text() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    expected = build_provider_observation()

    result = analyzer._extract_structured_json(
        {
            "output_text": json.dumps(
                expected
            )
        }
    )

    assert result == expected


def test_extracts_nested_output_text() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    expected = build_provider_observation()

    result = analyzer._extract_structured_json(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                expected
                            ),
                        }
                    ]
                }
            ]
        }
    )

    assert result == expected


def test_extract_rejects_provider_refusal() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    refusal = runtime_value("refusal")

    with pytest.raises(
        CloudVisualAnalyzerError,
        match=refusal,
    ):
        analyzer._extract_structured_json(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "refusal",
                                "refusal": refusal,
                            }
                        ]
                    }
                ]
            }
        )


def test_extract_rejects_non_json_output() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="non-JSON",
    ):
        analyzer._extract_structured_json(
            {
                "output_text": runtime_value(
                    "plain-text"
                )
            }
        )


def test_extract_rejects_missing_output() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    with pytest.raises(
        CloudVisualAnalyzerError,
        match="No structured",
    ):
        analyzer._extract_structured_json(
            {
                "output": [],
            }
        )


def test_normalization_clamps_confidence_values() -> None:
    analyzer = CloudVisualAnalyzer(
        build_configuration()
    )

    provider_observation = (
        build_provider_observation()
    )

    provider_observation["entities"][0][
        "confidence"
    ] = 4.5

    provider_observation["entities"][0][
        "attributes"
    ][0]["confidence"] = -2

    provider_observation["relations"][0][
        "confidence"
    ] = 3

    result = analyzer._normalize_provider_response(
        question=runtime_value("question"),
        image_path=runtime_value("image-path"),
        source_uri=runtime_value("source"),
        provider_json=provider_observation,
    )

    assert (
        result["entities"][0]["confidence"]
        == 1.0
    )

    assert (
        result["entities"][0]["attributes"][0][
            "confidence"
        ]
        == 0.0
    )

    assert (
        result["relations"][0]["confidence"]
        == 1.0
    )


def test_analyze_encodes_image_and_normalizes_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()
    key_value = runtime_value("key")

    monkeypatch.setenv(
        configuration.api_key_env_var,
        key_value,
    )

    image_bytes = b"runtime-image-bytes"
    image_path = tmp_path / "media.png"
    image_path.write_bytes(image_bytes)

    provider_observation = (
        build_provider_observation()
    )

    captured: dict[str, Any] = {}

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    def fake_post_json(
        *,
        url: str,
        api_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        captured["url"] = url
        captured["api_key"] = api_key
        captured["payload"] = payload

        return {
            "output_text": json.dumps(
                provider_observation
            )
        }

    monkeypatch.setattr(
        analyzer,
        "_post_json",
        fake_post_json,
    )

    result = analyzer.analyze(
        question=runtime_value("question"),
        image_path=str(image_path),
        source_uri=runtime_value("source"),
    )

    assert result["provider"] == "openai"
    assert result["model"] == configuration.model
    assert result["entities"]
    assert result["relations"]

    assert captured["url"] == (
        configuration.endpoint_url
    )

    assert captured["api_key"] == key_value

    image_input = next(
        item
        for item in captured["payload"][
            "input"
        ][1]["content"]
        if item["type"] == "input_image"
    )

    prefix = "data:image/png;base64,"

    assert image_input["image_url"].startswith(
        prefix
    )

    encoded_value = image_input[
        "image_url"
    ][len(prefix):]

    assert base64.b64decode(
        encoded_value
    ) == image_bytes


def test_analyze_does_not_return_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()
    secret_value = runtime_value("secret")

    monkeypatch.setenv(
        configuration.api_key_env_var,
        secret_value,
    )

    image_path = tmp_path / "media.png"
    image_path.write_bytes(b"runtime-media")

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    monkeypatch.setattr(
        analyzer,
        "_post_json",
        lambda **_: {
            "output_text": json.dumps(
                build_provider_observation()
            )
        },
    )

    result = analyzer.analyze(
        question=runtime_value("question"),
        image_path=str(image_path),
    )

    assert secret_value not in json.dumps(
        result
    )


def test_analyze_does_not_store_raw_provider_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = build_configuration()

    monkeypatch.setenv(
        configuration.api_key_env_var,
        runtime_value("key"),
    )

    image_path = tmp_path / "media.png"
    image_path.write_bytes(b"runtime-media")

    analyzer = CloudVisualAnalyzer(
        configuration
    )

    monkeypatch.setattr(
        analyzer,
        "_post_json",
        lambda **_: {
            "output_text": json.dumps(
                build_provider_observation()
            )
        },
    )

    result = analyzer.analyze(
        question=runtime_value("question"),
        image_path=str(image_path),
    )

    assert "provider_response" not in result


def contains_enum(
    value: Any,
) -> bool:
    if isinstance(value, dict):
        if "enum" in value:
            return True

        return any(
            contains_enum(item)
            for item in value.values()
        )

    if isinstance(value, list):
        return any(
            contains_enum(item)
            for item in value
        )

    return False
