"""
Proveedor de IA: GitHub Copilot (vía GitHub Models).

GitHub Copilot en sí no expone un endpoint público de "chat
completions" (requiere el flujo OAuth interno de VS Code/Copilot).
Lo que sí es público y funciona con un simple Personal Access Token
de GitHub es **GitHub Models** (https://github.com/marketplace/models):
un catálogo de modelos que se consume con una API compatible con la
de OpenAI, en `https://models.inference.ai.azure.com/chat/completions`.

Tanto `connect()` (una petición mínima de 1 token, solo para validar
el token) como `send_message()` (la conversación real) usan ese mismo
endpoint con peticiones HTTP reales.
"""
import json
from typing import Callable, Optional, Tuple

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

DEFAULT_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class GitHubCopilotProvider(AIProvider):
    """Integración con GitHub Copilot / GitHub Models (conexión y chat reales)."""

    name = "GitHub Copilot"

    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        if not api_key.strip():
            self._connected = False
            return False, "Debes ingresar un token de GitHub (API Key)"

        self._endpoint = endpoint.strip()
        self._api_key = api_key.strip()

        url = self._resolve_url(self._endpoint)
        headers = self._build_headers()
        # Petición mínima real: 1 solo token de salida, solo para
        # confirmar que el token es válido y el servicio responde.
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }

        status, _body, error = self._http_post(url, headers, payload)

        if status == 200:
            self._connected = True
            return True, "Conectado correctamente"

        self._connected = False
        return False, self._describe_error(status, error)

    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        if not self.is_connected():
            raise RuntimeError("GitHub Copilot no está conectado. Prueba la conexión en Configuración.")

        url = self._resolve_url(self._endpoint)
        headers = self._build_headers()
        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt),
            "max_tokens": 800,
        }

        status, body, error = self._http_post(url, headers, payload, timeout=CHAT_TIMEOUT_SECONDS)

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
            raise RuntimeError("GitHub Copilot no está conectado. Prueba la conexión en Configuración.")

        url = self._resolve_url(self._endpoint)
        headers = self._build_headers()
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
            url, headers, payload, handle_line, should_stop=should_stop, timeout=CHAT_TIMEOUT_SECONDS
        )

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        return "".join(collected)

    # ------------------------------------------------------------------ #
    # Utilidades internas
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_messages(message: str, system_prompt: Optional[str]) -> list[dict]:
        """Antepone un mensaje 'system' (ej. quién es el usuario) si se indica uno."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        return messages

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resolve_url(endpoint: str) -> str:
        """Usa el endpoint configurado por el usuario, o el de GitHub Models por defecto."""
        endpoint = endpoint.strip()
        if not endpoint:
            return DEFAULT_ENDPOINT
        if endpoint.endswith("/chat/completions"):
            return endpoint
        return f"{endpoint.rstrip('/')}/chat/completions"

    @staticmethod
    def _describe_error(status: int | None, error: str | None) -> str:
        if status == 401:
            return "Token de GitHub inválido o expirado (401 Unauthorized)"
        if status == 403:
            return "Acceso denegado (403 Forbidden) — revisa los permisos del token"
        if status == 404:
            return "Endpoint no encontrado (404)"
        if status == 429:
            return "Límite de solicitudes alcanzado (429 Too Many Requests)"
        if status is not None:
            return f"El servidor respondió con error HTTP {status}"
        return error or "No se pudo conectar"
