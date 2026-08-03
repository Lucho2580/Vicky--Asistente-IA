import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from core.microsoft_auth import SCOPES, TICKET_SCOPES, MicrosoftAuthService

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
REQUEST_TIMEOUT_SECONDS = 15


class GraphApiError(RuntimeError):
    pass


class GraphClient:
    """
    Wrapper delgado sobre Microsoft Graph, pensado para dos usos concretos:
      1. Leer correo del usuario logueado (para detectar solicitudes de ticket)
      2. Crear elementos en una Lista de SharePoint (para dar de alta el ticket)

    No maneja login: reutiliza el token cacheado por MicrosoftAuthService.
    Si no hay token disponible, todos los métodos devuelven un error claro
    en vez de romper — el llamador decide si le pide al usuario loguearse.
    """

    def __init__(self, auth_service: Optional[MicrosoftAuthService] = None) -> None:
        self._auth_service = auth_service or MicrosoftAuthService()

    def _request(
        self, method: str, path_or_url: str, json_body: Optional[dict] = None
    ) -> Tuple[Optional[int], Optional[dict], Optional[str]]:
        token = self._auth_service.get_cached_access_token(scopes=SCOPES + TICKET_SCOPES)
        if not token:
            return None, None, (
                "Esta función necesita permisos adicionales (correo y SharePoint) que todavía no están "
                "otorgados para tu cuenta. Puede ser que: (1) nunca se pidió ese permiso — probá desde la "
                "app la opción para habilitar tickets, o (2) un administrador de Microsoft 365 todavía no "
                "aprobó esos permisos para la app 'Asistente IA La Vianda' — en ese caso pedile a IT que "
                "otorgue el consentimiento en Microsoft Entra ID."
            )

        url = path_or_url if path_or_url.startswith("http") else f"{GRAPH_BASE}{path_or_url}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body else {}
                return response.status, parsed, None
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body else {}
                message = parsed.get("error", {}).get("message", exc.reason)
            except (json.JSONDecodeError, AttributeError):
                message = exc.reason
            return exc.code, None, f"Graph API error {exc.code}: {message}"
        except urllib.error.URLError as exc:
            return None, None, f"No se pudo conectar con Microsoft Graph: {exc.reason}"
        except json.JSONDecodeError as exc:
            return None, None, f"Respuesta inesperada de Graph: {exc}"

    # ------------------------------------------------------------------
    # Correo
    # ------------------------------------------------------------------

    def list_recent_messages(
        self, top: int = 25, filter_query: Optional[str] = None, folder: str = "Inbox"
    ) -> Tuple[bool, "list[dict] | str"]:
        """
        Lista mensajes recientes de una carpeta (por defecto la bandeja de
        entrada). filter_query usa la sintaxis OData de Graph, ej.:
            "from/emailAddress/address eq 'tickets@lavianda.com'"
        Devuelve (True, [mensajes]) o (False, "mensaje de error").
        """
        params = {"$top": str(top), "$orderby": "receivedDateTime desc"}
        if filter_query:
            params["$filter"] = filter_query
        query = urllib.parse.urlencode(params)
        path = f"/me/mailFolders/{folder}/messages?{query}"

        status, body, error = self._request("GET", path)
        if status != 200:
            return False, error or f"Graph respondió {status} al listar correos"
        return True, body.get("value", [])

    # ------------------------------------------------------------------
    # SharePoint
    # ------------------------------------------------------------------

    def resolve_site_id(self, hostname: str, site_path: str) -> Tuple[bool, str]:
        """
        Ayuda de configuración inicial (uso manual, una sola vez): dado
        'lavianda.sharepoint.com' y '/sites/IT', devuelve el site_id real
        que después va en la configuración de tickets.
        """
        path_clean = site_path.strip("/")
        status, body, error = self._request("GET", f"/sites/{hostname}:/{path_clean}")
        if status != 200:
            return False, error or f"No se pudo resolver el sitio (HTTP {status})"
        return True, body.get("id", "")

    def list_site_lists(self, site_id: str) -> Tuple[bool, "list[dict] | str"]:
        """
        Ayuda de configuración inicial: lista las Listas de un sitio para
        identificar el list_id y sus nombres de columna reales.
        """
        status, body, error = self._request("GET", f"/sites/{site_id}/lists")
        if status != 200:
            return False, error or f"No se pudo listar las listas del sitio (HTTP {status})"
        return True, body.get("value", [])

    def list_columns(self, site_id: str, list_id: str) -> Tuple[bool, "list[dict] | str"]:
        status, body, error = self._request("GET", f"/sites/{site_id}/lists/{list_id}/columns")
        if status != 200:
            return False, error or f"No se pudieron listar las columnas (HTTP {status})"
        return True, body.get("value", [])

    def create_list_item(self, site_id: str, list_id: str, fields: dict) -> Tuple[bool, "dict | str"]:
        """
        Crea un elemento nuevo en la Lista de SharePoint — el equivalente a
        enviar el Microsoft Form, pero directo al destino real de los datos.
        'fields' debe usar los nombres internos de columna de la lista
        (no siempre coinciden con el nombre visible; usar list_columns()
        para confirmarlos antes de la primera prueba).
        """
        status, body, error = self._request(
            "POST", f"/sites/{site_id}/lists/{list_id}/items", json_body={"fields": fields}
        )
        if status not in (200, 201):
            return False, error or f"No se pudo crear el ticket (HTTP {status})"
        return True, body
