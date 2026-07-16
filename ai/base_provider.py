"""
Interfaz base para proveedores de IA.

`connect()` realiza una prueba de conexión REAL contra el endpoint del
proveedor (HTTP), guarda el endpoint/API key usados (para que
`send_message()` pueda reutilizarlos) y devuelve tanto el éxito/fracaso
como un mensaje de diagnóstico legible para mostrar en la interfaz.

`send_message()` ya SÍ está implementado en los proveedores concretos
que tienen una API de chat pública (OpenAI, GitHub Models, Gemini):
hace una petición real y devuelve el texto de la respuesta, o lanza
una excepción con el motivo si algo falla.
"""
import json
import socket
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Tuple

DEFAULT_TIMEOUT_SECONDS = 6
CHAT_TIMEOUT_SECONDS = 30  # las respuestas de chat tardan más que un simple ping


class AIProvider(ABC):
    """Contrato común para cualquier motor de IA."""

    name: str = "Base"

    def __init__(self) -> None:
        self._connected = False
        self._endpoint = ""
        self._api_key = ""

    @abstractmethod
    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        """
        Intenta una conexión real contra el proveedor.

        Retorna (True, "Conectado correctamente") en éxito, o
        (False, "<motivo legible>") en caso de fallo (credenciales
        inválidas, endpoint vacío, timeout, sin red, etc.).
        """
        raise NotImplementedError

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def send_message(self, message: str) -> str:
        """
        Envía un mensaje real al proveedor y devuelve el texto de la
        respuesta. Las subclases con una API de chat pública la
        sobrescriben; si no hay una implementación real, se informa
        explícitamente en lugar de fingir una respuesta.
        """
        raise NotImplementedError(f"El envío de mensajes con {self.name} todavía no está implementado.")

    # ------------------------------------------------------------------ #
    # Utilidad compartida: hacer una petición HTTP real (GET o POST) y
    # clasificar el resultado. Toda subclase debe usar esto en lugar de
    # llamar a urllib directamente, para que el manejo de errores sea
    # consistente en toda la aplicación.
    # ------------------------------------------------------------------ #
    @classmethod
    def _http_request(
        cls,
        url: str,
        headers: dict,
        method: str = "GET",
        json_body: Any = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> Tuple[int | None, str | None, str | None]:
        """
        Realiza una petición HTTP real.

        Retorna (status_code, response_text, error):
            - Éxito: (status_code, cuerpo_de_la_respuesta, None)
            - Error HTTP (401/403/404/...): (status_code, cuerpo_si_lo_hay, motivo)
            - Sin respuesta (timeout, DNS, sin red): (None, None, "<motivo legible>")
        """
        data = None
        request_headers = dict(headers)
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, body, None
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = None
            return exc.code, body, exc.reason
        except urllib.error.URLError as exc:
            return None, None, f"No se pudo conectar: {exc.reason}"
        except socket.timeout:
            return None, None, "Tiempo de espera agotado"
        except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo de red
            return None, None, str(exc)

    @classmethod
    def _http_get(
        cls, url: str, headers: dict, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> Tuple[int | None, str | None, str | None]:
        return cls._http_request(url, headers, method="GET", timeout=timeout)

    @classmethod
    def _http_post(
        cls, url: str, headers: dict, json_body: Any, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> Tuple[int | None, str | None, str | None]:
        return cls._http_request(url, headers, method="POST", json_body=json_body, timeout=timeout)
