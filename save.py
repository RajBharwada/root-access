"""Tiny JSON save file: star ratings per level + user settings."""
import json
import os

PATH = os.path.join(os.path.expanduser("~"), ".root_access_save.json")


def default():
    return {"stars": {}, "settings": {"font_size": 20, "panel": True}}


def load():
    data = default()
    try:
        with open(PATH, encoding="utf-8") as f:
            loaded = json.load(f)
        data["stars"].update(loaded.get("stars", {}))
        data["settings"].update(loaded.get("settings", {}))
    except (OSError, ValueError, AttributeError):
        pass
    return data


def save(data):
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass