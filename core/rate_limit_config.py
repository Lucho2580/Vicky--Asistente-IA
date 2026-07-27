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
