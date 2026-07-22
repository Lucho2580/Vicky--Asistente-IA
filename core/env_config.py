import os
import sys
from pathlib import Path
from typing import List, Optional

from core.paths import USER_DATA_DIR

ENV_ENDPOINT_KEY = "ASISTENTEIA_AI_ENDPOINT"
ENV_API_KEY_KEY = "ASISTENTEIA_AI_API_KEY"
ENV_ENGINE_KEY = "ASISTENTEIA_AI_ENGINE"

# Actualizaciones: igual que el motor de IA, nunca acoplado a una URL
# fija — se puede centralizar por .env, sin tocar Configuración.
ENV_UPDATE_SOURCE_KEY = "ASISTENTEIA_UPDATE_SOURCE"          # "custom" | "github"
ENV_UPDATE_ENDPOINT_KEY = "ASISTENTEIA_UPDATE_ENDPOINT"        # URL propia (source="custom")
ENV_UPDATE_GITHUB_REPO_KEY = "ASISTENTEIA_UPDATE_GITHUB_REPO"  # "usuario/repositorio" (source="github")

_loaded = False


def _candidate_env_files() -> List[Path]:
    """Ubicaciones donde se busca un archivo .env, en orden de prioridad."""
    if getattr(sys, "frozen", False):
        # Ejecutable empaquetado con PyInstaller: junto al .exe.
        exe_dir = Path(sys.executable).resolve().parent
    else:
        # Corriendo desde el código fuente: raíz del proyecto.
        exe_dir = Path(__file__).resolve().parent.parent

    return [exe_dir / ".env", USER_DATA_DIR / ".env"]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # No se sobreescribe una variable de entorno real que ya
            # esté definida: el sistema siempre tiene prioridad sobre el .env.
            os.environ.setdefault(key, value)
    except OSError:
        pass  # el archivo no se puede leer: se ignora, no es un error crítico


def load_environment() -> None:
    """Carga cualquier archivo .env encontrado. Se puede llamar varias veces (idempotente)."""
    global _loaded
    if _loaded:
        return
    for path in _candidate_env_files():
        _load_env_file(path)
    _loaded = True


def get_ai_endpoint_from_env() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_ENDPOINT_KEY) or None


def get_ai_api_key_from_env() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_API_KEY_KEY) or None


def get_ai_engine_from_env() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_ENGINE_KEY) or None


def get_update_source_from_env() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_UPDATE_SOURCE_KEY) or None


def get_update_endpoint_from_env() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_UPDATE_ENDPOINT_KEY) or None


def get_update_github_repo_from_env() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_UPDATE_GITHUB_REPO_KEY) or None


def ai_credentials_from_env() -> bool:
    """True si el endpoint o la API Key de IA vienen de variables de entorno / .env."""
    return bool(get_ai_endpoint_from_env() or get_ai_api_key_from_env())
