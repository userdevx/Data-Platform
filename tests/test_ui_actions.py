from pathlib import Path

from engine.ui_actions import (
    create_database,
    data_setup_ready,
    open_source,
    paige_ready,
    run_ui_action,
    save_settings,
    settings_ready,
    workspace_refresh,
)


def test_workspace_refresh_returns_visible_response():
    result = workspace_refresh()

    assert result["status"] == "success"
    assert result["message"] == "Workspace loaded."
    assert isinstance(result["rows"], list)
    assert isinstance(result["data"], dict)


def test_data_setup_ready():
    result = data_setup_ready()

    assert result["status"] == "success"
    assert result["message"] == "Data setup ready."


def test_paige_ready():
    result = paige_ready()

    assert result["status"] == "success"
    assert result["message"] == "Paige ready."


def test_settings_ready():
    result = settings_ready()

    assert result["status"] == "success"
    assert result["message"] == "Settings ready."


def test_create_database_requires_file():
    result = create_database("test_database", "")

    assert result["status"] == "error"
    assert result["error"] == "missing_selected_file"


def test_create_database_success(tmp_path):
    sample_file = tmp_path / "sample.csv"
    sample_file.write_text("name,value\ncpu,online\n", encoding="utf-8")

    result = create_database("Sample Database", str(sample_file))

    assert result["status"] == "success"
    assert result["message"] == "Database created."
    assert result["rows"][0]["database_name"] == "sample_database"


def test_open_source_validates_url():
    result = open_source("not-a-url")

    assert result["status"] == "error"
    assert result["error"] == "invalid_url"


def test_save_settings_validates_email():
    result = save_settings({"email": "bad-email"})

    assert result["status"] == "error"
    assert result["error"] == "invalid_email"


def test_unknown_ui_action():
    result = run_ui_action("Unknown Button")

    assert result["status"] == "error"
    assert result["error"] == "unknown_action"
