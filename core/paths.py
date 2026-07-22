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


# Carpeta base de datos de usuario (escribible), NO la carpeta de instalación.
USER_DATA_DIR = _resolve_user_data_dir()

CONFIG_DIR = USER_DATA_DIR / "config"
LOGS_DIR = USER_DATA_DIR / "logs"

# Carpeta "Training": el usuario coloca aquí sus archivos de entrenamiento
# directamente desde el explorador de archivos (sin tener que subirlos uno
# por uno desde la app); la app la sincroniza automáticamente al iniciar.
# Vive en la carpeta de datos de usuario (escribible) por el mismo motivo
# que conversations.db/knowledge.db: si estuviera dentro de la carpeta de
# instalación (Archivos de programa), el usuario no podría escribir ahí.
TRAINING_DIR = USER_DATA_DIR / "Training"

CONVERSATIONS_DB_PATH = CONFIG_DIR / "conversations.db"
KNOWLEDGE_DB_PATH = CONFIG_DIR / "knowledge.db"
SETTINGS_PATH = CONFIG_DIR / "settings.json"

# Se crean por adelantado para que cualquier módulo que las use pueda
# asumir que ya existen (sqlite3, por ejemplo, no crea carpetas por sí solo).
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
