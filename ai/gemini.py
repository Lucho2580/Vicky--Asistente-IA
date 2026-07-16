"""
Proveedor de IA: Google Gemini.

`connect()` valida la API Key contra el listado de modelos.
`send_message()` usa el endpoint `generateContent` del modelo
`gemini-1.5-flash` para obtener una respuesta real. Ambas son
peticiones HTTP reales, sin simulaciones.
"""
import json
from typing import Tuple
from urllib.parse import quote

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(AIProvider):
    """Integración con Google Gemini (conexión y chat reales)."""

    name = "Gemini"

    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        if not api_key.strip():
            self._connected = False
            return False, "Debes ingresar una API Key"

        self._endpoint = endpoint.strip()
        self._api_key = api_key.strip()

        base_url = self._endpoint or MODELS_ENDPOINT
        url = f"{base_url}?key={quote(self._api_key)}"

        status, _body, error = self._http_get(url, headers={})

        if status == 200:
            self._connected = True
            return True, "Conectado correctamente"

        self._connected = False
        return False, self._describe_error(status, error)

    def send_message(self, message: str) -> str:
        if not self.is_connected():
            raise RuntimeError("Gemini no está conectado. Prueba la conexión en Configuración.")

        base_url = self._endpoint or MODELS_ENDPOINT
        url = f"{base_url}/{DEFAULT_MODEL}:generateContent?key={quote(self._api_key)}"
        payload = {"contents": [{"parts": [{"text": message}]}]}

        status, body, error = self._http_post(url, headers={}, json_body=payload, timeout=CHAT_TIMEOUT_SECONDS)

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        try:
            data = json.loads(body)
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Respuesta inesperada del servidor: {exc}")

    @staticmethod
    def _describe_error(status: int | None, error: str | None) -> str:
        if status == 400:
            return "API Key inválida o mal formada (400)"
        if status == 403:
            return "Acceso denegado (403 Forbidden)"
        if status == 429:
            return "Límite de solicitudes alcanzado (429 Too Many Requests)"
        if status is not None:
            return f"El servidor respondió con error HTTP {status}"
        return error or "No se pudo conectar"
