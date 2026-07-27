import os
import sys
from pathlib import Path

APP_DATA_DIR_NAME = "AsistenteIA-LaVianda"


def _resolve_user_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")

    return Path(base) / APP_DATA_DIR_NAME


USER_DATA_DIR = _resolve_user_data_dir()

CONFIG_DIR = USER_DATA_DIR / "config"
LOGS_DIR = USER_DATA_DIR / "logs"

TRAINING_DIR = USER_DATA_DIR / "Training"

CONVERSATIONS_DB_PATH = CONFIG_DIR / "conversations.db"
KNOWLEDGE_DB_PATH = CONFIG_DIR / "knowledge.db"
SETTINGS_PATH = CONFIG_DIR / "settings.json"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
