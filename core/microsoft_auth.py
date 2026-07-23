import os
from pathlib import Path
from typing import Callable, Optional, Tuple

from core.env_config import load_environment
from core.paths import USER_DATA_DIR

ENV_CLIENT_ID_KEY = "ASISTENTEIA_MS_CLIENT_ID"
ENV_TENANT_ID_KEY = "ASISTENTEIA_MS_TENANT_ID"

DEFAULT_TENANT_ID = "common"  # cuentas personales + de trabajo/escuela
GRAPH_ME_ENDPOINT = "https://graph.microsoft.com/v1.0/me"
SCOPES = ["User.Read"]

TOKEN_CACHE_PATH = USER_DATA_DIR / "ms_token_cache.bin"


def is_configured() -> bool:
    """True si hay un Client ID de Microsoft Entra configurado (ver docstring del módulo)."""
    load_environment()
    return bool(os.environ.get(ENV_CLIENT_ID_KEY))


def _get_client_id() -> Optional[str]:
    load_environment()
    return os.environ.get(ENV_CLIENT_ID_KEY) or None


def _get_tenant_id() -> str:
    load_environment()
    return os.environ.get(ENV_TENANT_ID_KEY) or DEFAULT_TENANT_ID


class MicrosoftAuthService:
    """Login con Microsoft (device code flow) + obtención del nombre real vía Graph."""

    def __init__(self) -> None:
        self._app = None  # se crea perezosamente, solo si is_configured()
        self._token_cache = None

    def _build_app(self):
        import msal  # import perezoso: si no está instalado, solo falla si de verdad se usa

        if self._token_cache is None:
            self._token_cache = msal.SerializableTokenCache()
            if TOKEN_CACHE_PATH.exists():
                try:
                    self._token_cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass  # caché corrupta o vacía: se ignora, se pedirá login de nuevo

        client_id = _get_client_id()
        authority = f"https://login.microsoftonline.com/{_get_tenant_id()}"
        # OJO: construir PublicClientApplication ya hace una llamada de red real
        # (descubre la configuración del tenant), no es diferido hasta el login.
        # Sin internet (o con ese dominio bloqueado), esto lanza una excepción,
        # por eso todo llamador de _build_app() debe envolverlo en try/except.
        return msal.PublicClientApplication(client_id, authority=authority, token_cache=self._token_cache)

    def _save_cache(self) -> None:
        if self._token_cache is not None and self._token_cache.has_state_changed:
            TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_CACHE_PATH.write_text(self._token_cache.serialize(), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Login silencioso (usa la sesión guardada de una vez anterior)
    # ------------------------------------------------------------------ #
    def try_silent_login(self) -> Optional[dict]:
        """
        Si ya hubo un login anterior en esta computadora, intenta renovar
        la sesión sin pedirle nada al usuario. Retorna el resultado del
        token (con `access_token`) o None si no hay sesión guardada o
        ya no es válida (hace falta volver a iniciar sesión).
        """
        if not is_configured():
            return None

        try:
            app = self._build_app()
        except Exception:  # noqa: BLE001 - sin internet, dominio bloqueado, etc.
            return None

        accounts = app.get_accounts()
        if not accounts:
            return None

        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        self._save_cache()
        if result and "access_token" in result:
            return result
        return None

    # ------------------------------------------------------------------ #
    # Login interactivo (código de dispositivo)
    # ------------------------------------------------------------------ #
    def login_with_device_code(
        self, on_code_ready: Callable[[str, str], None]
    ) -> Tuple[bool, Optional[dict], str]:
        """
        Inicia el login. Llama a `on_code_ready(codigo, url)` apenas
        Microsoft entrega el código de dispositivo, para que la UI lo
        muestre; después esta llamada BLOQUEA (pensada para correr en un
        hilo aparte) hasta que el usuario complete el login en el
        navegador o se agote el tiempo de espera.

        Retorna (éxito, resultado_del_token_o_None, mensaje).
        """
        if not is_configured():
            return False, None, (
                f"El login con Microsoft no está configurado todavía: falta la variable de entorno "
                f"{ENV_CLIENT_ID_KEY} con el Client ID de un App Registration de Microsoft Entra ID."
            )

        try:
            app = self._build_app()
        except Exception as exc:  # noqa: BLE001 - sin internet, tenant/client id inválido, etc.
            return False, None, f"No se pudo conectar con Microsoft: {exc}"

        try:
            flow = app.initiate_device_flow(scopes=SCOPES)
        except Exception as exc:  # noqa: BLE001
            return False, None, f"No se pudo iniciar el login con Microsoft: {exc}"

        if "user_code" not in flow:
            return False, None, flow.get("error_description", "Microsoft no devolvió un código de dispositivo válido.")

        on_code_ready(flow["user_code"], flow["verification_uri"])

        try:
            result = app.acquire_token_by_device_flow(flow)
        except Exception as exc:  # noqa: BLE001
            return False, None, f"Error esperando el login: {exc}"

        self._save_cache()

        if result and "access_token" in result:
            return True, result, "Sesión iniciada correctamente."

        error_description = (result or {}).get("error_description", "No se pudo completar el login.")
        return False, None, error_description

    # ------------------------------------------------------------------ #
    # Nombre real del usuario (vía Microsoft Graph)
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_display_name(token_result: dict) -> Optional[str]:
        """
        Llama a Microsoft Graph (`/me`) con el access token obtenido y
        devuelve el nombre real de la persona (de pila, si está
        disponible; si no, el nombre completo).
        """
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
        """Borra la sesión guardada (la próxima vez pedirá login de nuevo)."""
        if TOKEN_CACHE_PATH.exists():
            TOKEN_CACHE_PATH.unlink()
        self._token_cache = None
