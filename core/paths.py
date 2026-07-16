"""
Rutas compartidas del proyecto.

Punto único de verdad para ubicaciones de archivos usadas por varios
módulos (persistencia de conversaciones, logs, configuración), para
evitar que cada módulo calcule su propia ruta de forma independiente.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"

CONVERSATIONS_DB_PATH = CONFIG_DIR / "conversations.db"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
