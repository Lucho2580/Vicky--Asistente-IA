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


def _embedded_env_path() -> Optional[Path]:
    """
    Ruta del `.env` que el instalador (.msi) empaqueta junto al .exe
    (ver `.github/workflows/build-msi.yml`) — el mismo que hoy trae la
    API Key de IA en texto plano en cada instalación. `None` si esto no
    es un build empaquetado (correr desde código fuente no cuenta: ese
    `.env` es del desarrollador, no del instalador, y no se debe tocar
    sin que se dé cuenta).
    """
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent / ".env"


def consume_and_scrub_embedded_ai_api_key() -> None:
    """
    Se llama una sola vez, muy al principio del arranque (ver
    `main.py`), SOLO en el build empaquetado.

    Reduce la ventana de exposición de la API Key de IA que el
    instalador embebe en texto plano: si encuentra un valor real en el
    `.env` junto al .exe, lo migra al llavero seguro del sistema
    operativo (mismo mecanismo que `core/secure_settings.py` usa para
    lo que se guarda desde Configuración) y borra ese valor del
    archivo en disco — se mantiene la línea, mostrada vacía, en vez de
    eliminarla, para no romper el formato del archivo si un build
    futuro necesita volver a escribirla.

    IMPORTANTE — esto NO resuelve el problema de fondo (la key sigue
    siendo la misma para todas las instalaciones, y cualquiera con
    acceso a la sesión de Windows donde corre la app puede extraerla
    en tiempo de ejecución). Es una reducción de superficie: pasa de
    "la key queda en texto plano en disco todo el tiempo que la app
    esté instalada" a "solo hasta el primer arranque". La solución de
    fondo es el proxy backend (que evita que el cliente tenga la key).

    Si no hay un llavero seguro disponible en este equipo (ver
    `core/secure_settings.is_secure_storage_available`), no se toca el
    archivo: mejor dejar la key en texto plano y funcionando que
    borrarla sin tener dónde guardarla de forma segura.
    """
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
                new_lines.append(f"{ENV_API_KEY_KEY}=")  # línea conservada, valor vaciado
                continue
        new_lines.append(raw_line)

    if not api_key_value:
        return  # ya se migró en un arranque anterior, o nunca hubo key embebida

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
