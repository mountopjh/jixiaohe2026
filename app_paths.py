import os
import sys
from typing import Iterable


APP_DIR_NAME = "BankBin"
OLD_APP_DIR_NAME = "Jixiaohe"

if getattr(sys, "frozen", False):
    RUN_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", RUN_DIR)
else:
    RUN_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = RUN_DIR


def _dedupe_paths(paths: Iterable[str]) -> Iterable[str]:
    seen: set[str] = set()
    for path in paths:
        if not path:
            continue
        normalized = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        key = os.path.normcase(normalized)
        if key in seen:
            continue
        seen.add(key)
        yield normalized


def _candidate_data_roots() -> Iterable[str]:
    if os.name == "nt":
        yield os.getenv("APPDATA") or ""
        yield os.getenv("LOCALAPPDATA") or ""
        home = os.path.expanduser("~")
        if home and home != "~":
            yield os.path.join(home, "AppData", "Roaming")
            yield os.path.join(home, "AppData", "Local")
    else:
        yield os.getenv("XDG_DATA_HOME") or ""
        home = os.path.expanduser("~")
        if home and home != "~":
            yield os.path.join(home, ".local", "share")
            yield home


def _resolve_app_data_dir() -> str:
    errors: list[str] = []
    for root in _dedupe_paths(_candidate_data_roots()):
        path = os.path.join(root, APP_DIR_NAME)
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except OSError as exc:
            errors.append(f"{path}: {exc}")

    detail = "; ".join(errors) if errors else "no usable application data root found"
    raise RuntimeError(f"Cannot create {APP_DIR_NAME} data directory outside the executable directory: {detail}")


def _existing_app_data_dirs(app_dir_name: str) -> tuple[str, ...]:
    paths: list[str] = []
    for root in _dedupe_paths(_candidate_data_roots()):
        path = os.path.join(root, app_dir_name)
        if os.path.isdir(path):
            paths.append(path)
    return tuple(paths)


APP_DATA_DIR = _resolve_app_data_dir()
DB_PATH = os.path.join(APP_DATA_DIR, "bin_database.db")
SETTINGS_PATH = os.path.join(APP_DATA_DIR, "settings.json")
CRASH_LOG_PATH = os.path.join(APP_DATA_DIR, "crash_report.log")

OLD_APP_DATA_DIRS = _existing_app_data_dirs(OLD_APP_DIR_NAME)
OLD_DB_PATHS = tuple(os.path.join(path, "bin_database.db") for path in OLD_APP_DATA_DIRS)
OLD_SETTINGS_PATHS = tuple(os.path.join(path, "settings.json") for path in OLD_APP_DATA_DIRS)

LEGACY_DB_PATH = os.path.join(RUN_DIR, "bin_database.db")
LEGACY_SETTINGS_PATH = os.path.join(RUN_DIR, "settings.json")


def ensure_app_data_dir() -> str:
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    return APP_DATA_DIR
