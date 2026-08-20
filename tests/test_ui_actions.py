from uuid import uuid4
from engine.ui_actions import (
    create_database,
    data_setup_ready,
    open_source,
    intelligence_ready,
    run_pipeline,
    run_query,
    run_ui_action,
    save_settings,
    settings_ready,
    workspace_refresh,
)


def test_workspace_refresh_returns_visible_response(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = workspace_refresh()

    assert result["status"] == "success"
    assert result["message"] == "Workspace loaded."
    assert isinstance(result["rows"], list)
    assert isinstance(result["data"], dict)


def test_data_setup_ready(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = data_setup_ready()

    assert result["status"] == "success"
    assert result["message"] == "Data setup ready."


def test_intelligence_ready():
    result = intelligence_ready()

    assert result["status"] == "success"
    assert result["message"] == "Intelligence ready."


def test_settings_ready():
    result = settings_ready()

    assert result["status"] == "success"
    assert result["message"] == "Settings ready."


def test_create_database_requires_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = create_database("test_database", "")

    assert result["status"] == "error"
    assert result["error"] == "missing_selected_file"


def test_create_database_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    sample_file = tmp_path / "sample.csv"
    sample_file.write_text("name,value\ncpu,online\n", encoding="utf-8")

    result = create_database("Sample Database", str(sample_file))

    assert result["status"] == "success"
    assert result["message"] == "Database created."
    assert result["rows"][0]["database_name"] == "sample_database"
    assert (tmp_path / "data" / "databases" / "sample_database").exists()
    assert (tmp_path / "data_lake" / "raw" / "records.jsonl").exists()


def test_run_pipeline_after_database_creation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    sample_file = tmp_path / "sample.csv"
    sample_file.write_text("name,value\ncpu,online\n", encoding="utf-8")

    create_database("Sample Database", str(sample_file))
    result = run_pipeline()

    assert result["status"] == "success"
    assert result["message"] == "Pipeline complete."


def test_run_query_after_database_creation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    sample_file = tmp_path / "sample.csv"
    sample_file.write_text("name,value\ncpu,online\n", encoding="utf-8")

    create_database("Sample Database", str(sample_file))
    result = run_query()

    assert result["status"] == "success"
    assert result["message"] == "Query complete."
    assert len(result["rows"]) >= 1


def test_open_source_validates_url():
    result = open_source("not-a-url")

    assert result["status"] == "error"
    assert result["error"] == "invalid_url"


def test_open_source_accepts_valid_url():
    result = open_source("https://example.com")

    assert result["status"] == "success"
    assert result["message"] == "Source opened."


def test_save_settings_validates_email(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = save_settings({"email": "bad-email"})

    assert result["status"] == "error"
    assert result["error"] == "invalid_email"


def test_save_settings_success(tmp_path, monkeypatch):
    generated_display_name = f"identity-{uuid4().hex}"
    monkeypatch.chdir(tmp_path)

    result = save_settings(
        {
            "display_name": generated_display_name,
            "email": "user@example.com",
            "storage_limit": "500 MB",
            "privacy": "local_first",
        }
    )

    assert result["status"] == "success"
    assert result["message"] == "Settings updated."
    assert result["rows"][0]["email"] == "user@example.com"


def test_unknown_ui_action():
    result = run_ui_action("Unknown Button")

    assert result["status"] == "error"
    assert result["error"] == "unknown_action"
