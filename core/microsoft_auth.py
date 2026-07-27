import os
import stat
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple

from core.env_config import load_environment
from core.paths import USER_DATA_DIR

ENV_CLIENT_ID_KEY = "ASISTENTEIA_MS_CLIENT_ID"
ENV_TENANT_ID_KEY = "ASISTENTEIA_MS_TENANT_ID"

DEFAULT_TENANT_ID = "common"
GRAPH_ME_ENDPOINT = "https://graph.microsoft.com/v1.0/me"
SCOPES = ["User.Read"]

TOKEN_CACHE_PATH = USER_DATA_DIR / "ms_token_cache.bin"


def is_configured() -> bool:
    load_environment()
    return bool(os.environ.get(ENV_CLIENT_ID_KEY))


def _get_client_id() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_CLIENT_ID_KEY) or None


def _get_tenant_id() -> str:
    load_environment()
    return os.environ.get(ENV_TENANT_ID_KEY) or DEFAULT_TENANT_ID


class MicrosoftAuthService:

    def __init__(self) -> None:
        self._app = None
        self._token_cache = None

    def _build_app(self):
        import msal

        if self._token_cache is None:
            self._token_cache = msal.SerializableTokenCache()
            if TOKEN_CACHE_PATH.exists():
                try:
                    self._token_cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass

        client_id = _get_client_id()
        authority = f"https://login.microsoftonline.com/{_get_tenant_id()}"
        return msal.PublicClientApplication(client_id, authority=authority, token_cache=self._token_cache)

    def _save_cache(self) -> None:
        if self._token_cache is not None and self._token_cache.has_state_changed:
            TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_CACHE_PATH.write_text(self._token_cache.serialize(), encoding="utf-8")
            self._restrict_permissions(TOKEN_CACHE_PATH)

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        if sys.platform.startswith("win"):
            return
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def try_silent_login(self) -> Optional[dict]:
        if not is_configured():
            return None

        try:
            app = self._build_app()
        except Exception:
            return None

        accounts = app.get_accounts()
        if not accounts:
            return None

        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        self._save_cache()
        if result and "access_token" in result:
            return result
        return None

    def login_with_device_code(
        self, on_code_ready: Callable[[str, str], None]
    ) -> Tuple[bool, Optional[dict], str]:
        if not is_configured():
            return False, None, (
                f"El login con Microsoft no está configurado todavía: falta la variable de entorno "
                f"{ENV_CLIENT_ID_KEY} con el Client ID de un App Registration de Microsoft Entra ID."
            )

        try:
            app = self._build_app()
        except Exception as exc:
            return False, None, f"No se pudo conectar con Microsoft: {exc}"

        try:
            flow = app.initiate_device_flow(scopes=SCOPES)
        except Exception as exc:
            return False, None, f"No se pudo iniciar el login con Microsoft: {exc}"

        if "user_code" not in flow:
            return False, None, flow.get("error_description", "Microsoft no devolvió un código de dispositivo válido.")

        on_code_ready(flow["user_code"], flow["verification_uri"])

        try:
            result = app.acquire_token_by_device_flow(flow)
        except Exception as exc:
            return False, None, f"Error esperando el login: {exc}"

        self._save_cache()

        if result and "access_token" in result:
            return True, result, "Sesión iniciada correctamente."

        error_description = (result or {}).get("error_description", "No se pudo completar el login.")
        return False, None, error_description

    @staticmethod
    def get_display_name(token_result: dict) -> Optional[str]:
        access_token = token_result.get("access_token")
        if not access_token:
            return None

        import urllib.request
        import urllib.error
        import json

        request = urllib.request.Request(
            GRAPH_ME_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}, method="GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

        return data.get("givenName") or data.get("displayName")

    def logout(self) -> None:
        if TOKEN_CACHE_PATH.exists():
            TOKEN_CACHE_PATH.unlink()
        self._token_cache = None
