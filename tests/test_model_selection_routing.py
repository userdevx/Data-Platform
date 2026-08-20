from __future__ import annotations

from types import SimpleNamespace

import pytest

import engine.application.automatic_model_request_action as automatic_action
import engine.application.model_request_action as manual_action
from services.visual_model.provider_errors import (
    VisualProviderUnavailableError,
)


def _policy():
    return SimpleNamespace(
        prefer_local=True,
        allow_cloud_fallback=True,
        require_runtime_health_check=False,
        maximum_attempts=2,
    )


def _configuration():
    return SimpleNamespace(
        selection_policy=_policy(),
    )


def _descriptor(
    *,
    provider_id: str,
    model_id: str,
    processing_location: str,
):
    return SimpleNamespace(
        provider_id=provider_id,
        model_id=model_id,
        processing_location=SimpleNamespace(
            value=processing_location,
        ),
    )


def test_automatic_semantic_similarity_requires_comparison_input(
    monkeypatch,
):
    registry_called = False

    def fail_if_registry_is_built(_configuration):
        nonlocal registry_called
        registry_called = True

        raise AssertionError(
            "Automatic model selection must not "
            "start for an invalid request."
        )

    monkeypatch.setattr(
        automatic_action,
        "load_project_environment",
        lambda: None,
    )

    monkeypatch.setattr(
        automatic_action,
        "build_visual_provider_registry",
        fail_if_registry_is_built,
    )

    with pytest.raises(
        ValueError,
        match=(
            "semantic_similarity requires "
            "comparison_text or comparison_texts"
        ),
    ):
        automatic_action.process_automatic_model_request(
            question="fixture request",
            required_capability=(
                "semantic_similarity"
            ),
            arguments={},
        )

    assert registry_called is False


def test_automatic_selection_records_selected_model(
    monkeypatch,
):
    selected_descriptor = _descriptor(
        provider_id="provider-a",
        model_id="model-a",
        processing_location="local",
    )

    class FakeRegistry:
        def select_models(
            self,
            *,
            capability_request,
            require_runtime_health_check,
        ):
            assert (
                capability_request
                .required_capabilities
                == frozenset(
                    {
                        "semantic_similarity",
                    }
                )
            )

            assert (
                require_runtime_health_check
                is False
            )

            return [
                selected_descriptor,
            ]

    captured_request = {}

    def fake_manual_request(
        *,
        question,
        option_id,
        capability,
        arguments,
    ):
        captured_request.update(
            {
                "question": question,
                "option_id": option_id,
                "capability": capability,
                "arguments": arguments,
            }
        )

        return {
            "status": "success",
            "answer": "fixture result",
            "raw": {
                "provider_id": "provider-a",
                "model_id": "model-a",
                "capability": (
                    "semantic_similarity"
                ),
                "processing_location": "local",
                "route": (
                    "manual_model_selection"
                ),
                "metadata": {},
            },
        }

    monkeypatch.setattr(
        automatic_action,
        "load_project_environment",
        lambda: None,
    )

    monkeypatch.setattr(
        automatic_action,
        "load_visual_model_registry_configuration",
        lambda _path: _configuration(),
    )

    monkeypatch.setattr(
        automatic_action,
        "build_visual_provider_registry",
        lambda _configuration: FakeRegistry(),
    )

    monkeypatch.setattr(
        automatic_action,
        "process_manual_model_request",
        fake_manual_request,
    )

    result = (
        automatic_action
        .process_automatic_model_request(
            question="fixture request",
            required_capability=(
                "semantic_similarity"
            ),
            arguments={
                "comparison_text": (
                    "fixture comparison"
                ),
            },
        )
    )

    assert result["status"] == "success"

    assert (
        captured_request["option_id"]
        == "provider-a:model-a"
    )

    assert (
        captured_request["capability"]
        == "semantic_similarity"
    )

    raw = result["raw"]

    assert (
        raw["route"]
        == "automatic_model_selection"
    )

    assert raw["selection"] == {
        "required_capability": (
            "semantic_similarity"
        ),
        "candidate_count": 1,
        "selected_provider_id": (
            "provider-a"
        ),
        "selected_model_id": "model-a",
        "processing_location": "local",
    }


def test_automatic_selection_can_try_next_candidate(
    monkeypatch,
):
    descriptors = [
        _descriptor(
            provider_id="provider-a",
            model_id="model-a",
            processing_location="local",
        ),
        _descriptor(
            provider_id="provider-b",
            model_id="model-b",
            processing_location="cloud",
        ),
    ]

    class FakeRegistry:
        def select_models(
            self,
            *,
            capability_request,
            require_runtime_health_check,
        ):
            return descriptors

    attempted_options = []

    def fake_manual_request(
        *,
        question,
        option_id,
        capability,
        arguments,
    ):
        attempted_options.append(
            option_id
        )

        if option_id == "provider-a:model-a":
            raise VisualProviderUnavailableError(
                "fixture provider unavailable"
            )

        return {
            "status": "success",
            "answer": "fixture result",
            "raw": {
                "provider_id": "provider-b",
                "model_id": "model-b",
                "capability": "text_input",
                "processing_location": "cloud",
                "route": (
                    "manual_model_selection"
                ),
                "metadata": {},
            },
        }

    monkeypatch.setattr(
        automatic_action,
        "load_project_environment",
        lambda: None,
    )

    monkeypatch.setattr(
        automatic_action,
        "load_visual_model_registry_configuration",
        lambda _path: _configuration(),
    )

    monkeypatch.setattr(
        automatic_action,
        "build_visual_provider_registry",
        lambda _configuration: FakeRegistry(),
    )

    monkeypatch.setattr(
        automatic_action,
        "process_manual_model_request",
        fake_manual_request,
    )

    result = (
        automatic_action
        .process_automatic_model_request(
            question="fixture request",
            required_capability="text_input",
        )
    )

    assert attempted_options == [
        "provider-a:model-a",
        "provider-b:model-b",
    ]

    assert (
        result["raw"]["provider_id"]
        == "provider-b"
    )

    assert (
        result["raw"]["route"]
        == "automatic_model_selection"
    )


def test_manual_selection_rejects_unsupported_capability(
    monkeypatch,
):
    provider = SimpleNamespace(
        provider_id="provider-a",
        adapter_type="ollama",
        enabled=True,
    )

    descriptor = SimpleNamespace(
        provider_id="provider-a",
        model_id="model-a",
        capabilities=frozenset(
            {
                "text_input",
            }
        ),
        processing_location=(
            SimpleNamespace(
                value="local",
            )
        ),
    )

    execution_called = False

    def fail_if_model_executes(**_kwargs):
        nonlocal execution_called
        execution_called = True

        raise AssertionError(
            "An unsupported manual capability "
            "must not execute a model."
        )

    monkeypatch.setattr(
        manual_action,
        "load_project_environment",
        lambda: None,
    )

    monkeypatch.setattr(
        manual_action,
        "load_visual_model_registry_configuration",
        lambda _path: SimpleNamespace(),
    )

    monkeypatch.setattr(
        manual_action,
        "_resolve_selection",
        lambda **_kwargs: (
            provider,
            descriptor,
        ),
    )

    monkeypatch.setattr(
        manual_action,
        "_ask_ollama",
        fail_if_model_executes,
    )

    with pytest.raises(
        VisualProviderUnavailableError,
        match=(
            "does not support the required "
            "capability: semantic_similarity"
        ),
    ):
        manual_action.process_manual_model_request(
            question="fixture request",
            option_id="provider-a:model-a",
            capability=(
                "semantic_similarity"
            ),
            arguments={
                "comparison_text": (
                    "fixture comparison"
                ),
            },
        )

    assert execution_called is False


def test_manual_selection_rejects_automatic_option(
    monkeypatch,
):
    monkeypatch.setattr(
        manual_action,
        "load_project_environment",
        lambda: None,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Automatic requests must use "
            "the Intelligence Layer"
        ),
    ):
        manual_action.process_manual_model_request(
            question="fixture request",
            option_id="automatic",
        )
