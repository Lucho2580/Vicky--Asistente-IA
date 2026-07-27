import os
import sys
from pathlib import Path
from typing import List, Optional

from core.paths import USER_DATA_DIR

ENV_ENDPOINT_KEY = "ASISTENTEIA_AI_ENDPOINT"
ENV_API_KEY_KEY = "ASISTENTEIA_AI_API_KEY"
ENV_ENGINE_KEY = "ASISTENTEIA_AI_ENGINE"

ENV_UPDATE_SOURCE_KEY = "ASISTENTEIA_UPDATE_SOURCE"
ENV_UPDATE_ENDPOINT_KEY = "ASISTENTEIA_UPDATE_ENDPOINT"
ENV_UPDATE_GITHUB_REPO_KEY = "ASISTENTEIA_UPDATE_GITHUB_REPO"

_loaded = False


def _candidate_env_files() -> List[Path]:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
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
            os.environ.setdefault(key, value)
    except OSError:
        pass


def load_environment() -> None:
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
    return bool(get_ai_endpoint_from_env() or get_ai_api_key_from_env())


def _embedded_env_path() -> Optional[Path]:
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent / ".env"


def consume_and_scrub_embedded_ai_api_key() -> None:
    from core.app_logger import get_logger
    from core.secure_settings import set_secret

    env_path = _embedded_env_path()
    if env_path is None or not env_path.exists():
        return

    try:
        original_lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        get_logger().error("No se pudo leer el .env embebido para migrar la API Key: %s", exc)
        return

    api_key_value: Optional[str] = None
    new_lines: List[str] = []

    for raw_line in original_lines:
        stripped = raw_line.strip()
        if stripped.startswith(f"{ENV_API_KEY_KEY}=") and not stripped.startswith("#"):
            value = stripped[len(ENV_API_KEY_KEY) + 1:].strip().strip('"').strip("'")
            if value:
                api_key_value = value
                new_lines.append(f"{ENV_API_KEY_KEY}=")
                continue
        new_lines.append(raw_line)

    if not api_key_value:
        return

    if not set_secret("ai_api_key", api_key_value):
        get_logger().warning(
            "No se pudo migrar la API Key embebida al llavero seguro (sin backend "
            "disponible en este equipo): se deja el .env sin modificar para no "
            "perder la configuración."
        )
        return

    try:
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except OSError as exc:
        get_logger().error(
            "La API Key se migró al llavero, pero no se pudo limpiar el .env en disco: %s", exc
        )
        return

    get_logger().info(
        "API Key de IA embebida migrada al llavero seguro del sistema operativo "
        "y eliminada del .env en disco."
    )
