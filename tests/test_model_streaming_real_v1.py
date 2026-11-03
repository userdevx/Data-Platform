"""Real local-model checks for generation profiles and streaming.

Every test here calls the local model runtime named in the model
registry. Nothing is simulated. They run only when
DATAWORC_REAL_MODEL_TESTS=1 is set, because each one takes real model
time on this machine.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

from engine.application import model_request_action
from engine.application.automatic_model_request_action import (
    process_automatic_model_request,
)
from engine.application.model_options_action import (
    REGISTRY_CONFIGURATION_PATH,
)
from services.visual_model.provider_configuration import (
    load_visual_model_registry_configuration,
)
from services.visual_model.provider_errors import (
    VisualProviderRequestError,
    VisualProviderResponseError,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("DATAWORC_REAL_MODEL_TESTS") != "1",
    reason="real local-model test; set DATAWORC_REAL_MODEL_TESTS=1",
)


def _option_for(capability: str) -> str:
    configuration = load_visual_model_registry_configuration(
        REGISTRY_CONFIGURATION_PATH
    )

    for provider in configuration.providers:
        if not provider.enabled or provider.adapter_type != "ollama":
            continue

        for model in provider.models:
            if model.enabled and capability in model.capabilities:
                return f"{provider.provider_id}:{model.model_id}"

    pytest.fail(f"No enabled local model declares {capability}.")


def _profiles(tmp_path, monkeypatch, entry):
    path = tmp_path / "generation_profiles.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default": {"num_predict": 384, "num_ctx": 8192},
                "capabilities": {"code_generation": entry},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        model_request_action,
        "GENERATION_PROFILES_PATH",
        path,
    )


def test_chat_request_is_unchanged():
    result = model_request_action.process_manual_model_request(
        question="Reply with: ok",
        option_id=_option_for("text_input"),
        capability="text_input",
    )

    metadata = result["raw"]["metadata"]

    assert result["answer"].strip()
    assert metadata["streamed"] is False
    assert metadata["num_predict"] == 384
    assert metadata["processing_location"] == "local"
    print("CHAT_METADATA", metadata)


def test_output_limit_is_reported_not_hidden(tmp_path, monkeypatch):
    _profiles(
        tmp_path,
        monkeypatch,
        {
            "num_predict": 16,
            "stream": True,
            "reject_truncated": True,
            "idle_timeout_seconds": 300,
            "total_timeout_seconds": 600,
        },
    )

    with pytest.raises(VisualProviderResponseError, match="output limit"):
        model_request_action.process_manual_model_request(
            question="Write a Python function that sorts a list "
            "of dictionaries by a key, with a docstring.",
            option_id=_option_for("code_generation"),
            capability="code_generation",
        )


def test_idle_timeout_stops_a_silent_model(tmp_path, monkeypatch):
    _profiles(
        tmp_path,
        monkeypatch,
        {
            "num_predict": 64,
            "stream": True,
            "idle_timeout_seconds": 1,
            "total_timeout_seconds": 60,
        },
    )

    # A long, unique prompt: the model sends nothing until it has read
    # all of it, which takes far longer than one second on this CPU.
    filler = "\n".join(
        f"Line {index}: {uuid.uuid4().hex} {uuid.uuid4().hex}"
        for index in range(300)
    )

    with pytest.raises(VisualProviderRequestError, match="no output for 1 seconds"):
        model_request_action.process_manual_model_request(
            question="Count the lines below.\n" + filler,
            option_id=_option_for("code_generation"),
            capability="code_generation",
        )


def test_code_generation_streams_past_the_chat_limit():
    events: list[dict] = []

    result = process_automatic_model_request(
        question=(
            "Write a complete, self-contained Python module of about "
            "120 lines: a command-line to-do list manager with add, "
            "list, complete and delete commands, JSON file "
            "persistence, a docstring on every function, and a "
            "unittest.TestCase that covers each command. Output only "
            "the Python code."
        ),
        required_capability="code_generation",
        on_progress=events.append,
    )

    raw = result["raw"]
    metadata = raw["metadata"]

    print(
        "CODE_METADATA",
        {key: metadata.get(key) for key in (
            "generation_profile",
            "streamed",
            "eval_count",
            "prompt_eval_count",
            "done_reason",
            "num_predict",
            "total_duration",
        )},
        "model",
        raw.get("model_id"),
        "events",
        len(events),
    )

    assert metadata["generation_profile"] == "code_generation"
    assert metadata["streamed"] is True
    assert metadata["done_reason"] == "stop"
    assert metadata["eval_count"] > 384
    assert len(events) > 384 // 4
    assert "".join(event["text"] for event in events).strip() == result["answer"]
    assert all(event["event"] == "model_output" for event in events)
