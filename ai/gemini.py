import json
from typing import Callable, Optional, Tuple

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(AIProvider):

    name = "Gemini"

    def supports_vision(self) -> bool:
        return True

    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        if not api_key.strip():
            self._connected = False
            return False, "Debes ingresar una API Key"

        self._endpoint = endpoint.strip()
        self._api_key = api_key.strip()

        base_url = self._endpoint or MODELS_ENDPOINT
        status, _body, error = self._http_get(base_url, headers=self._auth_headers())

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
            raise RuntimeError("Gemini no está conectado. Prueba la conexión en Configuración.")
        self._enforce_rate_limit()

        base_url = self._endpoint or MODELS_ENDPOINT
        url = f"{base_url}/{DEFAULT_MODEL}:generateContent"
        payload = self._build_payload(message, system_prompt, history, image_base64, image_mime_type)

        status, body, error = self._http_post(
            url, headers=self._auth_headers(), json_body=payload, timeout=CHAT_TIMEOUT_SECONDS
        )

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        try:
            data = json.loads(body)
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
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
            raise RuntimeError("Gemini no está conectado. Prueba la conexión en Configuración.")
        self._enforce_rate_limit()

        base_url = self._endpoint or MODELS_ENDPOINT
        url = f"{base_url}/{DEFAULT_MODEL}:streamGenerateContent?alt=sse"
        payload = self._build_payload(message, system_prompt, history, image_base64, image_mime_type)

        collected: list[str] = []

        def handle_line(line: str) -> None:
            if not line.startswith("data:"):
                return
            payload_str = line[len("data:"):].strip()
            if not payload_str:
                return
            try:
                chunk = json.loads(payload_str)
                text = chunk["candidates"][0]["content"]["parts"][0]["text"]
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                return
            if text:
                collected.append(text)
                on_token(text)

        status, error = self._http_post_stream(
            url,
            headers=self._auth_headers(),
            json_body=payload,
            on_line=handle_line,
            should_stop=should_stop,
            timeout=CHAT_TIMEOUT_SECONDS,
        )

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        return "".join(collected)

    def _auth_headers(self) -> dict:
        return {"x-goog-api-key": self._api_key}

    @staticmethod
    def _build_payload(
        message: str,
        system_prompt: Optional[str],
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> dict:
        contents = []
        for turn in history or []:
            gemini_role = "model" if turn["role"] == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": turn["content"]}]})

        parts = [{"text": message}]
        if image_base64:
            parts.append(
                {"inline_data": {"mime_type": image_mime_type or "image/png", "data": image_base64}}
            )
        contents.append({"role": "user", "parts": parts})

        payload = {"contents": contents}
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
        return payload

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
