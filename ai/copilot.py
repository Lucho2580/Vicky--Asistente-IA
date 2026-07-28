import json
from typing import Callable, Optional, Tuple

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

DEFAULT_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class GitHubCopilotProvider(AIProvider):

    name = "GitHub Copilot"

    def supports_vision(self) -> bool:
        return True

    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        if not api_key.strip():
            self._connected = False
            return False, "Debes ingresar un token de GitHub (API Key)"

        self._endpoint = endpoint.strip()
        self._api_key = api_key.strip()

        url = self._resolve_url(self._endpoint)
        headers = self._build_headers()
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

    def send_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.is_connected():
            raise RuntimeError("GitHub Copilot no está conectado. Prueba la conexión en Configuración.")
        self._enforce_rate_limit()

        url = self._resolve_url(self._endpoint)
        headers = self._build_headers()
        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt, history, image_base64, image_mime_type),
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
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.is_connected():
            raise RuntimeError("GitHub Copilot no está conectado. Prueba la conexión en Configuración.")
        self._enforce_rate_limit()

        url = self._resolve_url(self._endpoint)
        headers = self._build_headers()
        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt, history, image_base64, image_mime_type),
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

    @staticmethod
    def _build_messages(
        message: str,
        system_prompt: Optional[str],
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for turn in history or []:
            messages.append({"role": turn["role"], "content": turn["content"]})

        if image_base64:
            mime = image_mime_type or "image/png"
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_base64}"}},
                ],
            })
        else:
            messages.append({"role": "user", "content": message})
        return messages

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resolve_url(endpoint: str) -> str:
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
