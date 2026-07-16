"""
Gestor de configuración de la aplicación.

Lee y escribe config/settings.json. Se mantiene deliberadamente simple
(sin lógica de conexión real todavía) ya que, según el alcance actual,
solo se necesita persistir las preferencias de interfaz (tema, motor de
IA seleccionado, datos de conexión a futuro).
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from core.paths import SETTINGS_PATH


@dataclass
class AppSettings:
    """Modelo de la configuración persistente de la aplicación."""

    theme: str = "light"
    ai_engine: str = "Offline"
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
                return AppSettings(**{**asdict(AppSettings()), **raw})
            except (json.JSONDecodeError, TypeError):
                return AppSettings()
        return AppSettings()

    @property
    def settings(self) -> AppSettings:
        return self._settings

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
