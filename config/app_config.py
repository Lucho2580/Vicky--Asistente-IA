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
from core.secure_settings import SECRET_FIELDS, get_secret, is_secure_storage_available, set_secret


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
                raw = {}
                settings = AppSettings()
        else:
            raw = {}
            settings = AppSettings()

        needs_migration = self._apply_secure_secrets(settings, raw)
        self._apply_env_overrides(settings)

        if needs_migration:
            # Había secretos en texto plano en el JSON (instalación
            # previa a este cambio, o el llavero no estaba disponible
            # en un guardado anterior): se acaban de migrar al llavero
            # seguro dentro de `_apply_secure_secrets`. Se guarda de
            # inmediato para limpiar el texto plano del disco ya
            # mismo, en vez de esperar a que el usuario abra
            # Configuración.
            self._settings = settings
            self.save()

        return settings

    @staticmethod
    def _apply_secure_secrets(settings: AppSettings, raw: dict) -> bool:
        """
        Para cada campo secreto: si hay un valor en el llavero seguro,
        ese manda (fuente de verdad). Si no, pero el JSON en disco
        trae un valor en texto plano (instalación anterior a este
        cambio), se conserva ese valor para no perder la
        configuración y se intenta migrar al llavero ahora mismo.

        Retorna True si hubo algún secreto en texto plano que migrar
        (para que `_load` dispare un `save()` inmediato y lo borre del
        JSON).
        """
        found_plaintext_to_migrate = False
        for field in SECRET_FIELDS:
            secure_value = get_secret(field)
            if secure_value:
                setattr(settings, field, secure_value)
                continue

            plaintext_value = raw.get(field, "")
            if plaintext_value:
                if set_secret(field, plaintext_value):
                    found_plaintext_to_migrate = True
                # Si set_secret devuelve False (sin llavero disponible
                # en este equipo), `plaintext_value` ya quedó en
                # `settings` por el merge de arriba: se sigue
                # funcionando en modo de respaldo (texto plano), igual
                # que antes de este cambio.

        return found_plaintext_to_migrate

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
        data = asdict(self._settings)

        for field in SECRET_FIELDS:
            value = data[field]
            stored_securely = set_secret(field, value)
            if stored_securely:
                # El valor real vive en el llavero del SO: no se
                # duplica en texto plano en el JSON.
                data[field] = ""
            # Si no hay llavero disponible, `data[field]` se deja tal
            # cual (texto plano) para no perder la configuración —
            # mismo comportamiento que antes de este cambio.

        SETTINGS_PATH.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    def update(self, **kwargs) -> None:
        """Actualiza uno o más campos y persiste inmediatamente."""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self.save()

    @property
    def secure_storage_available(self) -> bool:
        """
        True si las credenciales se están cifrando en el llavero real
        del sistema operativo. False si este equipo no tiene un
        backend de llavero disponible y se está usando el respaldo en
        texto plano (la UI de Configuración puede usar esto para
        avisarle al usuario).
        """
        return is_secure_storage_available()
