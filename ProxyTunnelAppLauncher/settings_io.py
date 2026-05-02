import json
import os

from .models import AppSettings

SETTINGS_FILE = "settings.json"


def load_settings(path: str = SETTINGS_FILE) -> AppSettings:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return AppSettings.from_dict(data)
        except Exception:
            pass
    return AppSettings()


def save_settings(settings: AppSettings, path: str = SETTINGS_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
