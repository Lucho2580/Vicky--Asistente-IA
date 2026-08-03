import os
import stat
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple

from core.app_logger import get_logger
from core.env_config import load_environment
from core.paths import USER_DATA_DIR

ENV_CLIENT_ID_KEY = "ASISTENTEIA_MS_CLIENT_ID"
ENV_TENANT_ID_KEY = "ASISTENTEIA_MS_TENANT_ID"

DEFAULT_TENANT_ID = "common"
GRAPH_ME_ENDPOINT = "https://graph.microsoft.com/v1.0/me"

# El login básico (para poder abrir la app y chatear) solo necesita "User.Read",
# que NUNCA requiere aprobación de un administrador de Microsoft 365 — por eso
# funcionaba antes para cualquier cuenta corporativa.
SCOPES = ["User.Read"]

# Estos son permisos ADICIONALES, separados del login básico, que solo se piden
# cuando alguien efectivamente usa la función de tickets (leer correo / escribir
# en la Lista de SharePoint). Mail.Read y Sites.ReadWrite.All suelen requerir
# consentimiento de un administrador de Microsoft 365 — si no está otorgado,
# Microsoft muestra la pantalla de "Se necesita la aprobación del administrador".
# Por eso NO van mezclados con el login básico: así ese bloqueo afecta solo a
# quien intenta crear/revisar tickets, no a todo el que abre la app.
# Si tu organización prefiere acotar el acceso a un único sitio en vez de "todos
# los sitios", se puede reemplazar Sites.ReadWrite.All por Sites.Selected, pero
# eso exige un paso extra de configuración (otorgar acceso a ese sitio puntual
# vía Graph con permisos de aplicación) que no se puede hacer solo con este
# login de usuario.
TICKET_SCOPES = ["Mail.Read", "Sites.ReadWrite.All"]

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

    def try_silent_login(self, scopes: Optional[list] = None) -> Optional[dict]:
        scopes = scopes or SCOPES

        if not is_configured():
            return None

        try:
            app = self._build_app()
        except Exception as exc:
            get_logger().warning("Login silencioso: no se pudo construir la app MSAL: %s", exc)
            return None

        accounts = app.get_accounts()
        if not accounts:
            get_logger().info("Login silencioso: no hay ninguna cuenta cacheada todavía.")
            return None

        try:
            result = app.acquire_token_silent(scopes, account=accounts[0])
        except Exception as exc:
            get_logger().warning("Login silencioso: acquire_token_silent lanzó una excepción: %s", exc)
            return None

        self._save_cache()

        if result and "access_token" in result:
            return result

        error = (result or {}).get("error")
        error_description = (result or {}).get("error_description")
        if error:
            # Con los scopes básicos (User.Read) esto casi no debería pasar.
            # Con TICKET_SCOPES (Mail.Read, Sites.ReadWrite.All) es esperable
            # si un administrador de Microsoft 365 todavía no aprobó esos
            # permisos para la app — en ese caso hace falta consentimiento de
            # admin, no alcanza con loguearse de nuevo como usuario normal.
            get_logger().info(
                "Login silencioso no disponible para scopes %s (%s): %s",
                scopes, error, error_description,
            )
        return None

    def login_with_device_code(
        self, on_code_ready: Callable[[str, str], None], scopes: Optional[list] = None
    ) -> Tuple[bool, Optional[dict], str]:
        scopes = scopes or SCOPES

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
            flow = app.initiate_device_flow(scopes=scopes)
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

        error = (result or {}).get("error", "")
        error_description = (result or {}).get("error_description", "No se pudo completar el login.")
        if "admin" in error_description.lower() or error in ("access_denied", "unauthorized_client"):
            error_description = (
                "Tu cuenta de Microsoft 365 necesita que un administrador apruebe permisos "
                "adicionales para esta app (Mail.Read, Sites.ReadWrite.All, usados para la función "
                "de tickets). Pedile a IT que otorgue el consentimiento, o iniciá sesión únicamente "
                "para usar el chat (sin tickets) si esto pasó al intentar usar esa función."
            )
        return False, None, error_description

    @staticmethod
    def get_display_name(token_result: dict) -> Optional[str]:
        profile = MicrosoftAuthService.get_profile(token_result)
        if not profile:
            return None
        return profile.get("givenName") or profile.get("displayName")

    @staticmethod
    def get_profile(token_result: dict) -> Optional[dict]:
        """
        Trae el perfil completo de la cuenta logueada desde Microsoft Graph
        (/me) — nombre, correo, cargo, área y sede — para mostrarlo en el
        panel de perfil de la app. Devuelve None si no se pudo consultar.
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

        return {
            "displayName": data.get("displayName"),
            "givenName": data.get("givenName"),
            "email": data.get("mail") or data.get("userPrincipalName"),
            "jobTitle": data.get("jobTitle"),
            "department": data.get("department"),
            "officeLocation": data.get("officeLocation"),
        }

    def get_cached_access_token(self, scopes: Optional[list] = None) -> Optional[str]:
        """
        Devuelve un access token válido usando solo el caché local (sin
        interacción). Lo usan los servicios en segundo plano (ej. el chequeo
        periódico de correo para tickets) que no pueden mostrarle un código
        de login a nadie. Por defecto pide solo los scopes del login básico;
        las funciones de tickets deben pasar explícitamente TICKET_SCOPES
        (combinados con SCOPES) para no afectar el login normal de nadie.
        Si no hay sesión cacheada con esos scopes, devuelve None — quien
        llama debe pedirle al usuario que otorgue ese permiso puntual.
        """
        result = self.try_silent_login(scopes=scopes)
        if result and "access_token" in result:
            return result["access_token"]
        return None

    def request_ticket_scopes(
        self, on_code_ready: Callable[[str, str], None]
    ) -> Tuple[bool, Optional[dict], str]:
        """
        Login interactivo (device code) pidiendo específicamente los scopes
        de tickets (Mail.Read, Sites.ReadWrite.All) además del login básico.
        Se usa solo cuando alguien intenta crear/revisar tickets y no hay
        todavía un token cacheado con esos permisos — nunca durante el login
        normal de la app.
        """
        return self.login_with_device_code(on_code_ready, scopes=SCOPES + TICKET_SCOPES)

    def logout(self) -> None:
        if TOKEN_CACHE_PATH.exists():
            TOKEN_CACHE_PATH.unlink()
        self._token_cache = None
