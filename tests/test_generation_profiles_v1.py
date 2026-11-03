"""Configuration checks for per-capability generation profiles.

No model is involved: these validate the settings file and its loader.
"""

from __future__ import annotations

import json

import pytest

from engine.application import model_request_action
from engine.application.generation_profiles import (
    PRE_PROFILE_BEHAVIOUR,
    load_generation_profile,
)
from services.visual_model.provider_errors import (
    VisualProviderConfigurationError,
)


def _write(tmp_path, document):
    path = tmp_path / "generation_profiles.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_missing_file_keeps_pre_profile_behaviour(tmp_path):
    profile = load_generation_profile(
        tmp_path / "absent.json",
        "code_generation",
    )

    assert profile == PRE_PROFILE_BEHAVIOUR
    assert profile.num_predict == 384
    assert profile.stream is False


def test_repository_configuration_keeps_chat_unchanged():
    path = model_request_action.GENERATION_PROFILES_PATH

    assert path.is_file(), path

    chat = load_generation_profile(path, "text_input")
    code = load_generation_profile(path, "code_generation")

    assert (chat.num_predict, chat.num_ctx, chat.stream) == (
        PRE_PROFILE_BEHAVIOUR.num_predict,
        PRE_PROFILE_BEHAVIOUR.num_ctx,
        False,
    )
    assert chat.reject_truncated is False

    assert code.stream is True
    assert code.reject_truncated is True
    assert code.num_predict > chat.num_predict
    assert code.num_predict < code.num_ctx
    assert code.idle_timeout_seconds <= code.total_timeout_seconds


def test_capability_inherits_default(tmp_path):
    path = _write(
        tmp_path,
        {
            "schema_version": 1,
            "default": {"num_predict": 100, "num_ctx": 2048},
            "capabilities": {"code_generation": {"num_predict": 900}},
        },
    )

    profile = load_generation_profile(path, "CODE_GENERATION")

    assert profile.name == "code_generation"
    assert profile.num_predict == 900
    assert profile.num_ctx == 2048
    assert load_generation_profile(path, "text_input").num_predict == 100


@pytest.mark.parametrize(
    "entry, message",
    [
        ({"num_predict": 0}, "positive integer"),
        ({"num_predict": True}, "positive integer"),
        ({"num_predict": 9000}, "smaller than num_ctx"),
        ({"stream": "yes"}, "true or false"),
        ({"stream": True}, "streaming requires"),
        (
            {
                "stream": True,
                "idle_timeout_seconds": 50,
                "total_timeout_seconds": 10,
            },
            "cannot exceed",
        ),
        ({"max_tokens": 10}, "unknown fields"),
    ],
)
def test_invalid_entries_are_rejected(tmp_path, entry, message):
    path = _write(
        tmp_path,
        {"schema_version": 1, "capabilities": {"code_generation": entry}},
    )

    with pytest.raises(VisualProviderConfigurationError, match=message):
        load_generation_profile(path, "text_input")


def test_schema_version_is_required(tmp_path):
    path = _write(tmp_path, {"capabilities": {}})

    with pytest.raises(VisualProviderConfigurationError, match="schema_version"):
        load_generation_profile(path, "text_input")
