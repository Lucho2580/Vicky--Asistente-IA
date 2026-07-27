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

    auto_check_updates: bool = True
    check_updates_on_startup: bool = True
    update_channel: str = "estable"
    update_frequency: str = "diaria"
    update_source: str = "custom"
    update_endpoint: str = ""
    update_github_repo: str = ""
    last_update_check: str = ""
    silent_updates_enabled: bool = False


class AppConfig:

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
            self._settings = settings
            self.save()

        return settings

    @staticmethod
    def _apply_secure_secrets(settings: AppSettings, raw: dict) -> bool:
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

        return found_plaintext_to_migrate

    @staticmethod
    def _apply_env_overrides(settings: AppSettings) -> None:
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
        return bool(get_ai_endpoint_from_env() or get_ai_api_key_from_env())

    def save(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self._settings)

        for field in SECRET_FIELDS:
            value = data[field]
            stored_securely = set_secret(field, value)
            if stored_securely:
                data[field] = ""

        SETTINGS_PATH.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self.save()

    @property
    def secure_storage_available(self) -> bool:
        return is_secure_storage_available()
