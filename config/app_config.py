import json
from dataclasses import asdict, dataclass

from core.env_config import (
    get_ai_api_key_from_env,
    get_ai_endpoint_from_env,
    get_ai_engine_from_env,
    get_update_endpoint_from_env,
    get_update_github_repo_from_env,
    get_update_source_from_env,
)
from core.paths import SETTINGS_PATH


@dataclass
class AppSettings:
    """Modelo de la configuración persistente de la aplicación."""

    theme: str = "light"
    ai_engine: str = "GitHub Copilot"
    ai_endpoint: str = ""
    ai_api_key: str = ""
    connection_string: str = ""
    db_server: str = ""
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    language: str = "es"
    ui_scale: str = "100%"
    version: int = 1

    # --- Actualizaciones ---
    auto_check_updates: bool = True
    check_updates_on_startup: bool = True
    update_channel: str = "estable"       # "estable" | "beta"
    update_frequency: str = "diaria"       # "diaria" | "semanal" | "manual"
    update_source: str = "custom"           # "custom" (endpoint propio) | "github"
    update_endpoint: str = ""                # URL del endpoint propio (source="custom")
    update_github_repo: str = ""              # "usuario/repositorio" (source="github")
    last_update_check: str = ""                # ISO 8601 del último chequeo realizado
    silent_updates_enabled: bool = False        # preparado, deshabilitado por defecto


class AppConfig:
    """Punto único de acceso a la configuración (carga perezosa + caché)."""

    _instance: "AppConfig | None" = None

    def __new__(cls) -> "AppConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = cls._instance._load()
        return cls._instance

    def _load(self) -> AppSettings:
        if SETTINGS_PATH.exists():
            try:
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                settings = AppSettings(**{**asdict(AppSettings()), **raw})
            except (json.JSONDecodeError, TypeError):
                settings = AppSettings()
        else:
            settings = AppSettings()

        self._apply_env_overrides(settings)
        return settings

    @staticmethod
    def _apply_env_overrides(settings: AppSettings) -> None:
        """Si hay variables de entorno / .env con el token o la URL, tienen prioridad."""
        env_endpoint = get_ai_endpoint_from_env()
        env_api_key = get_ai_api_key_from_env()
        env_engine = get_ai_engine_from_env()

        if env_endpoint:
            settings.ai_endpoint = env_endpoint
        if env_api_key:
            settings.ai_api_key = env_api_key
        if env_engine:
            settings.ai_engine = env_engine

        env_update_source = get_update_source_from_env()
        env_update_endpoint = get_update_endpoint_from_env()
        env_update_github_repo = get_update_github_repo_from_env()

        if env_update_source:
            settings.update_source = env_update_source
        if env_update_endpoint:
            settings.update_endpoint = env_update_endpoint
        if env_update_github_repo:
            settings.update_github_repo = env_update_github_repo

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def ai_credentials_locked(self) -> bool:
        """
        True si el endpoint o la API Key de IA vienen de variables de
        entorno / .env. En ese caso, la UI de Configuración debe
        mostrarlos como solo lectura (no tendría sentido dejar
        editarlos ahí si en el próximo inicio se van a sobreescribir
        con el valor de la variable de entorno de todos modos).
        """
        return bool(get_ai_endpoint_from_env() or get_ai_api_key_from_env())

    def save(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(asdict(self._settings), indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    def update(self, **kwargs) -> None:
        """Actualiza uno o más campos y persiste inmediatamente."""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self.save()
