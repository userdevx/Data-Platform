from engine.config import load_settings
from engine.storage.json_backend import LocalJsonStorageBackend


def get_backend():
    settings = load_settings()
    backend_name = settings["default_backend"]

    if backend_name == "local_json":
        return LocalJsonStorageBackend(settings["data_file"])

    raise ValueError(f"Unsupported backend: {backend_name}")
