import json
import os
import tempfile
from typing import Any

from app_paths import LEGACY_SETTINGS_PATH, OLD_SETTINGS_PATHS, SETTINGS_PATH, ensure_app_data_dir


def _load_json_dict(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_settings() -> dict[str, Any]:
    settings = _load_json_dict(SETTINGS_PATH)
    if settings is not None:
        return settings

    for legacy_path in (*OLD_SETTINGS_PATHS, LEGACY_SETTINGS_PATH):
        if os.path.abspath(legacy_path) == os.path.abspath(SETTINGS_PATH):
            continue
        legacy_settings = _load_json_dict(legacy_path)
        if legacy_settings is not None:
            save_settings(legacy_settings)
            return legacy_settings

    return {}


def save_settings(settings: dict[str, Any]) -> None:
    if not isinstance(settings, dict):
        settings = {}

    data_dir = ensure_app_data_dir()
    fd, tmp_path = tempfile.mkstemp(prefix="settings_", suffix=".json", dir=data_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, SETTINGS_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
