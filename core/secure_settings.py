from typing import Optional

from core.app_logger import get_logger

_KEYRING_SERVICE_NAME = "AsistenteIA-LaVianda"

SECRET_FIELDS = ("ai_api_key", "db_password", "connection_string")

_keyring_module = None
_keyring_available: Optional[bool] = None


def _get_keyring():
    global _keyring_module, _keyring_available
    if _keyring_available is not None:
        return _keyring_module if _keyring_available else None

    try:
        import keyring
        import keyring.errors

        keyring.get_password(_KEYRING_SERVICE_NAME, "__availability_probe__")
        _keyring_module = keyring
        _keyring_available = True
    except Exception as exc:
        get_logger().warning(
            "Llavero seguro del sistema operativo no disponible (%s). "
            "Las credenciales se guardarán en texto plano como respaldo — "
            "se recomienda instalar/soportar un backend de keyring en este equipo.",
            exc,
        )
        _keyring_module = None
        _keyring_available = False

    return _keyring_module


def is_secure_storage_available() -> bool:
    return _get_keyring() is not None


def get_secret(field: str) -> str:
    keyring = _get_keyring()
    if keyring is None:
        return ""
    try:
        return keyring.get_password(_KEYRING_SERVICE_NAME, field) or ""
    except Exception as exc:
        get_logger().error("No se pudo leer '%s' del llavero seguro: %s", field, exc)
        return ""


def set_secret(field: str, value: str) -> bool:
    keyring = _get_keyring()
    if keyring is None:
        return False

    try:
        if value:
            keyring.set_password(_KEYRING_SERVICE_NAME, field, value)
        else:
            try:
                keyring.delete_password(_KEYRING_SERVICE_NAME, field)
            except keyring.errors.PasswordDeleteError:
                pass
        return True
    except Exception as exc:
        get_logger().error("No se pudo guardar '%s' en el llavero seguro: %s", field, exc)
        return False
