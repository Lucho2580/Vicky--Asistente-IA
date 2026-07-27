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

SALVAGUARDA DE GASTO (mitigación temporal, ver `RateLimiter` más abajo)
------------------------------------------------------------------------
Hoy la API Key de IA se distribuye embebida (vía .env) en todas las
instalaciones de la app, en texto plano. Mientras se implementa el
proxy backend propio (que evita que el cliente tenga la key), esta
clase aplica un límite local de solicitudes por minuto/día como
salvaguarda adicional: no evita que alguien extraiga la key del
instalador y la use fuera de la app, pero sí acota el gasto que puede
generarse *desde la app misma* (bucles, mal uso accidental, un usuario
individual abusando del asistente). La protección real y completa
sigue siendo configurar límites de gasto/alcance en el panel del
proveedor (ver `core/rate_limit_config.py`).
"""
import json
import socket
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable, Optional, Tuple

DEFAULT_TIMEOUT_SECONDS = 6
CHAT_TIMEOUT_SECONDS = 30  # las respuestas de chat tardan más que un simple ping


class RateLimitExceededError(RuntimeError):
    """
    Se alcanzó el límite local de solicitudes configurado como
    salvaguarda de gasto (ver docstring del módulo). No es un error de
    red ni del proveedor: es una barrera puesta a propósito por esta
    aplicación.
    """


class RateLimiter:
    """
    Ventanas deslizantes simples (minuto + día) para acotar cuántas
    solicitudes puede hacer esta instancia de la app a un proveedor de
    IA. En memoria de proceso (no persiste entre reinicios): es una
    salvaguarda contra bucles y mal uso en una sesión, no un control de
    cuota estricto de nivel servidor — eso solo el proveedor puede
    garantizarlo (ver `core/rate_limit_config.py`).
    """

    def __init__(self, max_per_minute: int, max_per_day: int) -> None:
        self._max_per_minute = max_per_minute
        self._max_per_day = max_per_day
        self._minute_window: deque = deque()
        self._day_window: deque = deque()

    def check_and_record(self) -> None:
        """
        Lanza `RateLimitExceededError` si ya se alcanzó algún límite;
        si no, registra esta solicitud y deja pasar.
        """
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
    """Contrato común para cualquier motor de IA."""

    name: str = "Base"

    def __init__(self) -> None:
        self._connected = False
        self._endpoint = ""
        self._api_key = ""
        self._rate_limiter = RateLimiter(*self._load_rate_limits())

    @staticmethod
    def _load_rate_limits() -> Tuple[int, int]:
        """
        Lee los límites configurados (por admin, vía Configuración o
        .env). Import perezoso para evitar un ciclo de imports (
        `config.app_config` no depende de `ai`, pero se prefiere no
        importarlo a nivel de módulo en un paquete de bajo nivel como
        `ai/`).
        """
        from core.rate_limit_config import get_max_requests_per_day, get_max_requests_per_minute

        return get_max_requests_per_minute(), get_max_requests_per_day()

    def _enforce_rate_limit(self) -> None:
        """
        Cada proveedor concreto llama a esto al principio de
        `send_message()`/`send_message_stream()`, antes de gastar un
        solo token real. Lanza `RateLimitExceededError` si corresponde
        (ver `RateLimiter` arriba).
        """
        self._rate_limiter.check_and_record()

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

    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Envía un mensaje real al proveedor y devuelve el texto de la
        respuesta. `system_prompt`, si se pasa, se envía como mensaje de
        rol "system" (ej. quién es el usuario logueado), para que el
        modelo tenga ese contexto sin que el usuario tenga que repetirlo
        en cada pregunta. Las subclases con una API de chat pública la
        sobrescriben; si no hay una implementación real, se informa
        explícitamente en lugar de fingir una respuesta.
        """
        raise NotImplementedError(f"El envío de mensajes con {self.name} todavía no está implementado.")

    def send_message_stream(
        self,
        message: str,
        on_token: Callable[[str], None],
        should_stop: Optional[Callable[[], bool]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Igual que `send_message`, pero llama a `on_token(fragmento)` por
        cada pedazo de texto recibido en tiempo real, en vez de esperar
        toda la respuesta de una sola vez (streaming, como ChatGPT).

        Implementación por defecto: si una subclase no soporta
        streaming real, degrada de forma elegante llamando a
        `send_message()` una sola vez y entregando todo el texto como
        un único "fragmento" — sigue funcionando, solo que sin el
        efecto incremental.

        `should_stop`, si se pasa, se consulta periódicamente; si
        devuelve True, se corta la respuesta apenas sea posible (botón
        "Detener").
        """
        full_text = self.send_message(message, system_prompt=system_prompt)
        if not (should_stop and should_stop()):
            on_token(full_text)
        return full_text

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

    @staticmethod
    def _parse_openai_style_sse_line(line: str) -> Optional[str]:
        """
        Extrae el fragmento de texto (delta) de una línea de streaming en
        el formato que usan tanto OpenAI como GitHub Models (son
        compatibles entre sí): líneas "data: {...}" con
        choices[0].delta.content, terminando en "data: [DONE]".
        Devuelve None si la línea no trae texto nuevo (vacía, [DONE], o
        un campo distinto como el rol).
        """
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
        """
        Como `_http_post`, pero para streaming real: en vez de esperar
        toda la respuesta, llama a `on_line(línea)` por cada línea que
        llega del servidor en tiempo real (formato Server-Sent Events,
        que es como OpenAI/GitHub Models/Gemini transmiten el streaming).

        `should_stop` se consulta antes de procesar cada línea; si
        devuelve True, se corta la lectura ahí mismo (botón "Detener").

        Retorna (status_code, error). Si status_code == 200, on_line ya
        se encargó de todo el contenido recibido.
        """
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
            except Exception:  # noqa: BLE001
                body = None
            return exc.code, body or exc.reason
        except urllib.error.URLError as exc:
            return None, f"No se pudo conectar: {exc.reason}"
        except socket.timeout:
            return None, "Tiempo de espera agotado"
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)
