"""
Configuración de los límites locales de solicitudes a proveedores de
IA (ver `ai/base_provider.RateLimiter`).

Esto es una salvaguarda TEMPORAL mientras se implementa el proxy
backend propio (que va a sacar la API Key del cliente por completo).
No reemplaza los límites de gasto que hay que configurar del lado del
proveedor (OpenAI, Google AI Studio, GitHub) — esos son la única
protección real contra una key ya extraída y usada fuera de la app.
Ver el checklist en el propio repo / conversación con el equipo.

Los valores se pueden ajustar sin tocar código, vía variables de
entorno (mismo mecanismo que el resto de la configuración de IA):

    ASISTENTEIA_AI_MAX_REQUESTS_PER_MINUTE=20
    ASISTENTEIA_AI_MAX_REQUESTS_PER_DAY=300

Si no se configuran, se usan los valores por defecto de abajo —
pensados para uso normal de un asistente interno (una persona
escribiendo mensajes uno por uno), generosos para eso pero lo
suficientemente bajos como para frenar un bucle o un uso automatizado
que dispare cientos de solicitudes por minuto.
"""
import os

from core.env_config import load_environment

ENV_MAX_PER_MINUTE_KEY = "ASISTENTEIA_AI_MAX_REQUESTS_PER_MINUTE"
ENV_MAX_PER_DAY_KEY = "ASISTENTEIA_AI_MAX_REQUESTS_PER_DAY"

DEFAULT_MAX_REQUESTS_PER_MINUTE = 20
DEFAULT_MAX_REQUESTS_PER_DAY = 300


def _read_positive_int_env(key: str, default: int) -> int:
    load_environment()
    raw_value = os.environ.get(key)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def get_max_requests_per_minute() -> int:
    return _read_positive_int_env(ENV_MAX_PER_MINUTE_KEY, DEFAULT_MAX_REQUESTS_PER_MINUTE)


def get_max_requests_per_day() -> int:
    return _read_positive_int_env(ENV_MAX_PER_DAY_KEY, DEFAULT_MAX_REQUESTS_PER_DAY)
