from pathlib import Path

import pytest

from engine.application_generation.builder import (
    ApplicationBuilderService,
    encode_value,
    render_content,
    validation_source,
)
from engine.application_generation.request_router import (
    ApplicationRoutingError,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("user_prompt", "expected"),
    [
        ("Build a website for my business", "web-basic"),
        (
            "Create a Linux desktop application",
            "python-desktop-basic",
        ),
        ("Build a CSV processing utility", "python-data-basic"),
        (
            "Create an automation tool",
            "python-automation-basic",
        ),
    ],
)
def test_routes_registered_capability(user_prompt, expected):
    service = ApplicationBuilderService(ROOT)
    decision = service.router.route(user_prompt)

    assert decision.template_id == expected
    assert decision.candidates == (expected,)


def test_ambiguous_request_fails_closed():
    service = ApplicationBuilderService(ROOT)

    with pytest.raises(ApplicationRoutingError):
        service.router.route(
            "Build a website that processes CSV files"
        )


def test_unsupported_request_fails_closed():
    service = ApplicationBuilderService(ROOT)

    with pytest.raises(ApplicationRoutingError):
        service.router.route("Build an inventory system")


def test_unverified_platform_fails_closed():
    service = ApplicationBuilderService(ROOT)

    with pytest.raises(ApplicationRoutingError):
        service.router.route(
            "Build an Android website application"
        )


def test_python_rendering_preserves_values():
    result = render_content(
        "APP_NAME = __APP_NAME__\n"
        "REQUEST = __REQUEST__\n",
        project_name="inventory",
        request='Process "records"',
        mode="python-string",
    )

    assert 'APP_NAME = "inventory"' in result
    assert 'REQUEST = "Process \\"records\\""' in result


def test_html_rendering_escapes_text():
    result = render_content(
        "<h1>__APP_NAME__</h1>"
        "<p>__REQUEST__</p>",
        project_name="inventory",
        request="<script>alert(1)</script>",
        mode="html",
    )

    assert "&lt;script&gt;" in result
    assert "<script>" not in result


def test_real_production_templates_load():
    service = ApplicationBuilderService(ROOT)

    for template_id in (
        "web-basic",
        "python-desktop-basic",
        "python-data-basic",
        "python-automation-basic",
    ):
        definition = service.catalog.get(template_id)
        files = service.catalog.read_files(template_id)

        assert len(files) == 1
        assert definition.files[0].destination in files


def test_python_validator_uses_compilation():
    source = validation_source(
        ["src/main.py"],
        "python",
    )

    assert "compile(source, name, 'exec')" in source
    assert "exec(" not in source
    compile(source, "<validator>", "exec")
