"""
Proveedor de IA: OpenAI.

`connect()` valida la API Key con un GET real a `/v1/models`.
`send_message()` usa `/v1/chat/completions` con esa misma API Key para
obtener una respuesta real del modelo. Ambas son peticiones HTTP
reales, sin simulaciones.
"""
import json
from typing import Callable, Optional, Tuple

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

MODELS_ENDPOINT = "https://api.openai.com/v1/models"
CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(AIProvider):
    """Integración con la API de OpenAI (conexión y chat reales)."""

    name = "OpenAI"

    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        if not api_key.strip():
            self._connected = False
            return False, "Debes ingresar una API Key"

        self._endpoint = endpoint.strip()
        self._api_key = api_key.strip()

        url = self._endpoint or MODELS_ENDPOINT
        headers = {"Authorization": f"Bearer {self._api_key}"}

        status, _body, error = self._http_get(url, headers)

        if status == 200:
            self._connected = True
            return True, "Conectado correctamente"

        self._connected = False
        return False, self._describe_error(status, error)

    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        if not self.is_connected():
            raise RuntimeError("OpenAI no está conectado. Prueba la conexión en Configuración.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt),
            "max_tokens": 800,
        }

        status, body, error = self._http_post(CHAT_ENDPOINT, headers, payload, timeout=CHAT_TIMEOUT_SECONDS)

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        try:
            data = json.loads(body)
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Respuesta inesperada del servidor: {exc}")

    def send_message_stream(
        self,
        message: str,
        on_token: Callable[[str], None],
        should_stop: Optional[Callable[[], bool]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not self.is_connected():
            raise RuntimeError("OpenAI no está conectado. Prueba la conexión en Configuración.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt),
            "max_tokens": 800,
            "stream": True,
        }

        collected: list[str] = []

        def handle_line(line: str) -> None:
            delta = self._parse_openai_style_sse_line(line)
            if delta:
                collected.append(delta)
                on_token(delta)

        status, error = self._http_post_stream(
            CHAT_ENDPOINT, headers, payload, handle_line, should_stop=should_stop, timeout=CHAT_TIMEOUT_SECONDS
        )

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        return "".join(collected)

    @staticmethod
    def _build_messages(message: str, system_prompt: Optional[str]) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        return messages

    @staticmethod
    def _describe_error(status: int | None, error: str | None) -> str:
        if status == 401:
            return "API Key inválida (401 Unauthorized)"
        if status == 403:
            return "Acceso denegado (403 Forbidden)"
        if status == 429:
            return "Límite de solicitudes alcanzado (429 Too Many Requests)"
        if status is not None:
            return f"El servidor respondió con error HTTP {status}"
        return error or "No se pudo conectar"
