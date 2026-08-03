import json
from typing import Callable, Optional, Tuple

from ai.base_provider import CHAT_TIMEOUT_SECONDS, AIProvider

DEFAULT_MODEL = "llama3.1:8b-instruct-q4_K_M"
EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_ENDPOINT = "http://localhost:11434"


class LlamaProvider(AIProvider):
    """
    Proveedor para un modelo Llama servido internamente vía Ollama (por
    ejemplo, corriendo en un NAS/servidor propio de la empresa). No requiere
    API Key: el "endpoint" es la URL base del servidor Ollama
    (ej. http://192.168.1.50:11434).
    """

    name = "Llama (interno)"

    def supports_vision(self) -> bool:
        return False

    def supports_dictation(self) -> bool:
        return False

    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        self._endpoint = (endpoint or DEFAULT_ENDPOINT).strip().rstrip("/")
        self._api_key = ""

        status, body, error = self._http_get(f"{self._endpoint}/api/tags", headers={})

        if status == 200:
            self._connected = True
            if not self._model_is_available(body, DEFAULT_MODEL):
                return True, (
                    f"Conectado, pero el modelo '{DEFAULT_MODEL}' no está descargado "
                    f"en el servidor. Ejecutá 'ollama pull {DEFAULT_MODEL}' en el NAS."
                )
            return True, "Conectado correctamente"

        self._connected = False
        return False, self._describe_error(status, error)

    @staticmethod
    def _model_is_available(body: Optional[str], model_name: str) -> bool:
        if not body:
            return False
        try:
            data = json.loads(body)
            names = {m.get("name") for m in data.get("models", [])}
            return model_name in names
        except (json.JSONDecodeError, AttributeError, TypeError):
            return False

    def send_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.is_connected():
            raise RuntimeError("Llama no está conectado. Revisá la configuración del servidor interno.")
        self._enforce_rate_limit()

        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt, history),
            "stream": False,
        }

        status, body, error = self._http_post(
            f"{self._endpoint}/v1/chat/completions", {}, payload, timeout=CHAT_TIMEOUT_SECONDS
        )

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
            raise RuntimeError("Llama no está conectado. Revisá la configuración del servidor interno.")
        self._enforce_rate_limit()

        payload = {
            "model": DEFAULT_MODEL,
            "messages": self._build_messages(message, system_prompt, history),
            "stream": True,
        }

        collected: list[str] = []

        def handle_line(line: str) -> None:
            delta = self._parse_openai_style_sse_line(line)
            if delta:
                collected.append(delta)
                on_token(delta)

        status, error = self._http_post_stream(
            f"{self._endpoint}/v1/chat/completions", {}, payload, handle_line,
            should_stop=should_stop, timeout=CHAT_TIMEOUT_SECONDS,
        )

        if status != 200:
            self._connected = False
            raise RuntimeError(self._describe_error(status, error))

        return "".join(collected)

    def embed(self, text: str) -> Optional[list]:
        if not self.is_connected():
            return None

        payload = {"model": EMBEDDING_MODEL, "prompt": text[:8000]}
        status, body, _error = self._http_post(
            f"{self._endpoint}/api/embeddings", {}, payload, timeout=CHAT_TIMEOUT_SECONDS
        )
        if status != 200:
            return None

        try:
            data = json.loads(body)
            return data.get("embedding")
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _build_messages(message: str, system_prompt: Optional[str], history: Optional[list] = None) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for turn in history or []:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": message})
        return messages

    @staticmethod
    def _describe_error(status: Optional[int], error: Optional[str]) -> str:
        if status == 404:
            return "Endpoint no encontrado (404). Revisá la URL del servidor Ollama."
        if status is not None:
            return f"El servidor interno respondió con error HTTP {status}"
        return error or "No se pudo conectar al servidor Llama interno"
