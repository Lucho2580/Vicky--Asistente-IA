import json
import socket
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable, Optional, Tuple

DEFAULT_TIMEOUT_SECONDS = 6
CHAT_TIMEOUT_SECONDS = 30


class RateLimitExceededError(RuntimeError):
    pass


class RateLimiter:

    def __init__(self, max_per_minute: int, max_per_day: int) -> None:
        self._max_per_minute = max_per_minute
        self._max_per_day = max_per_day
        self._minute_window: deque = deque()
        self._day_window: deque = deque()

    def check_and_record(self) -> None:
        now = time.time()
        self._prune(self._minute_window, now, 60)
        self._prune(self._day_window, now, 86400)

        if self._max_per_minute and len(self._minute_window) >= self._max_per_minute:
            raise RateLimitExceededError(
                f"Se alcanzó el límite de {self._max_per_minute} solicitudes por minuto "
                "configurado como salvaguarda de gasto. Esperá un momento y reintentá."
            )
        if self._max_per_day and len(self._day_window) >= self._max_per_day:
            raise RateLimitExceededError(
                f"Se alcanzó el límite diario de {self._max_per_day} solicitudes "
                "configurado como salvaguarda de gasto. Se restablece mañana, o "
                "un administrador puede ajustarlo en Configuración."
            )

        self._minute_window.append(now)
        self._day_window.append(now)

    @staticmethod
    def _prune(window: deque, now: float, horizon_seconds: int) -> None:
        while window and (now - window[0]) > horizon_seconds:
            window.popleft()


class AIProvider(ABC):

    name: str = "Base"

    def __init__(self) -> None:
        self._connected = False
        self._endpoint = ""
        self._api_key = ""
        self._rate_limiter = RateLimiter(*self._load_rate_limits())

    @staticmethod
    def _load_rate_limits() -> Tuple[int, int]:
        from core.rate_limit_config import get_max_requests_per_day, get_max_requests_per_minute

        return get_max_requests_per_minute(), get_max_requests_per_day()

    def _enforce_rate_limit(self) -> None:
        self._rate_limiter.check_and_record()

    def embed(self, text: str) -> Optional[list]:
        """
        Calcula el vector de embedding de un texto, si este proveedor lo
        soporta. Devuelve None si no está soportado (la búsqueda semántica
        de la Base de Conocimiento cae de nuevo a la búsqueda por
        keywords en ese caso — nunca se rompe por esto).
        """
        return None

    @abstractmethod
    def connect(self, endpoint: str = "", api_key: str = "") -> Tuple[bool, str]:
        raise NotImplementedError

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def send_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        raise NotImplementedError(f"El envío de mensajes con {self.name} todavía no está implementado.")

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
        full_text = self.send_message(
            message,
            system_prompt=system_prompt,
            history=history,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
        )
        if not (should_stop and should_stop()):
            on_token(full_text)
        return full_text

    def supports_vision(self) -> bool:
        """True si este proveedor puede recibir imágenes adjuntas junto al mensaje."""
        return False

    @classmethod
    def _http_request(
        cls,
        url: str,
        headers: dict,
        method: str = "GET",
        json_body: Any = None,
        raw_body: Optional[bytes] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> Tuple[int | None, str | None, str | None]:
        data = None
        request_headers = dict(headers)
        if raw_body is not None:
            data = raw_body
        elif json_body is not None:
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
            except Exception:
                body = None
            return exc.code, body, exc.reason
        except urllib.error.URLError as exc:
            return None, None, f"No se pudo conectar: {exc.reason}"
        except socket.timeout:
            return None, None, "Tiempo de espera agotado"
        except Exception as exc:
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

    @classmethod
    def _http_post_raw(
        cls, url: str, headers: dict, raw_body: bytes, timeout: int = DEFAULT_TIMEOUT_SECONDS
    ) -> Tuple[int | None, str | None, str | None]:
        """Para subir contenido que no es JSON (ej. multipart/form-data con un archivo adjunto)."""
        return cls._http_request(url, headers, method="POST", raw_body=raw_body, timeout=timeout)

    def transcribe_audio(self, file_path: str) -> Optional[str]:
        """
        Transcribe un archivo de audio a texto, si este proveedor lo
        soporta. Devuelve None si no está soportado.
        """
        return None

    def supports_dictation(self) -> bool:
        """True si este proveedor puede transcribir audio a texto (chat de voz)."""
        return False

    @staticmethod
    def _parse_openai_style_sse_line(line: str) -> Optional[str]:
        if not line.startswith("data:"):
            return None
        payload_str = line[len("data:"):].strip()
        if not payload_str or payload_str == "[DONE]":
            return None
        try:
            chunk = json.loads(payload_str)
            return chunk["choices"][0]["delta"].get("content")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None

    @classmethod
    def _http_post_stream(
        cls,
        url: str,
        headers: dict,
        json_body: Any,
        on_line: Callable[[str], None],
        should_stop: Optional[Callable[[], bool]] = None,
        timeout: int = CHAT_TIMEOUT_SECONDS,
    ) -> Tuple[int | None, str | None]:
        request_headers = dict(headers)
        request_headers.setdefault("Content-Type", "application/json")
        data = json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                if status != 200:
                    body = response.read().decode("utf-8", errors="replace")
                    return status, body

                for raw_line in response:
                    if should_stop and should_stop():
                        break
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        on_line(line)
                return status, None
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = None
            return exc.code, body or exc.reason
        except urllib.error.URLError as exc:
            return None, f"No se pudo conectar: {exc.reason}"
        except socket.timeout:
            return None, "Tiempo de espera agotado"
        except Exception as exc:
            return None, str(exc)
