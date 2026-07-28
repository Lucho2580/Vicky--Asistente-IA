import json
from typing import Callable, Optional, Tuple

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

MODELS_ENDPOINT = "https://api.openai.com/v1/models"
CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
EMBEDDINGS_ENDPOINT = "https://api.openai.com/v1/embeddings"
TRANSCRIPTIONS_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
DEFAULT_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
TRANSCRIPTION_MODEL = "whisper-1"


class OpenAIProvider(AIProvider):

    name = "OpenAI"

    def supports_vision(self) -> bool:
        return True

    def supports_dictation(self) -> bool:
        return True

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

    def send_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.is_connected():
            raise RuntimeError("OpenAI no está conectado. Prueba la conexión en Configuración.")
        self._enforce_rate_limit()

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt, history, image_base64, image_mime_type),
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
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.is_connected():
            raise RuntimeError("OpenAI no está conectado. Prueba la conexión en Configuración.")
        self._enforce_rate_limit()

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
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
            CHAT_ENDPOINT, headers, payload, handle_line, should_stop=should_stop, timeout=CHAT_TIMEOUT_SECONDS
        )

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        return "".join(collected)

    def embed(self, text: str) -> Optional[list]:
        if not self.is_connected():
            return None

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": EMBEDDING_MODEL, "input": text[:8000]}

        status, body, _error = self._http_post(EMBEDDINGS_ENDPOINT, headers, payload, timeout=CHAT_TIMEOUT_SECONDS)
        if status != 200:
            return None

        try:
            data = json.loads(body)
            return data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

    def transcribe_audio(self, file_path: str) -> Optional[str]:
        if not self.is_connected():
            return None
        self._enforce_rate_limit()

        boundary = "----VickyBoundary7d9f1c3a"
        body = self._build_multipart_body(boundary, file_path, TRANSCRIPTION_MODEL)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        status, body_text, _error = self._http_post_raw(
            TRANSCRIPTIONS_ENDPOINT, headers, body, timeout=CHAT_TIMEOUT_SECONDS
        )
        if status != 200:
            return None

        try:
            data = json.loads(body_text)
            return data.get("text", "").strip() or None
        except (TypeError, json.JSONDecodeError):
            return None

    @staticmethod
    def _build_multipart_body(boundary: str, file_path: str, model: str) -> bytes:
        from pathlib import Path

        filename = Path(file_path).name
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        parts = [
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode("utf-8"),
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: audio/wav\r\n\r\n".encode("utf-8"),
            file_bytes,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
        return b"".join(parts)

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
