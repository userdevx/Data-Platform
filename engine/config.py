import json


SETTINGS_FILE = "config/settings.json"


def load_settings():
    with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)
