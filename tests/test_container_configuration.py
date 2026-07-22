from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "sandbox"


def load_compose(filename: str) -> dict:
    path = SANDBOX / filename
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def get_runtime_service(filename: str) -> dict:
    compose = load_compose(filename)
    return compose["services"]["intelligence-runtime"]


def test_restricted_profile_has_no_network() -> None:
    service = get_runtime_service(
        "docker-compose.intelligence.yml"
    )

    assert service["network_mode"] == "none"


def test_persistent_profile_has_no_network() -> None:
    service = get_runtime_service(
        "docker-compose.intelligence-persistent.yml"
    )

    assert service["network_mode"] == "none"


def test_all_profiles_use_read_only_root() -> None:
    filenames = [
        "docker-compose.intelligence.yml",
        "docker-compose.intelligence-persistent.yml",
        "docker-compose.intelligence-model.yml",
    ]

    for filename in filenames:
        service = get_runtime_service(filename)
        assert service["read_only"] is True


def test_all_profiles_drop_capabilities() -> None:
    filenames = [
        "docker-compose.intelligence.yml",
        "docker-compose.intelligence-persistent.yml",
        "docker-compose.intelligence-model.yml",
    ]

    for filename in filenames:
        service = get_runtime_service(filename)
        assert "ALL" in service["cap_drop"]


def test_all_profiles_disable_privilege_escalation() -> None:
    filenames = [
        "docker-compose.intelligence.yml",
        "docker-compose.intelligence-persistent.yml",
        "docker-compose.intelligence-model.yml",
    ]

    for filename in filenames:
        service = get_runtime_service(filename)

        assert (
            "no-new-privileges:true"
            in service["security_opt"]
        )


def test_model_profile_uses_configurable_ollama_address() -> None:
    service = get_runtime_service(
        "docker-compose.intelligence-model.yml"
    )

    environment = service["environment"]

    assert (
        environment["OLLAMA_BASE_URL"]
        == "http://host.docker.internal:11434"
    )
