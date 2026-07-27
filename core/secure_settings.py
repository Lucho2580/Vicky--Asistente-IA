"""
Almacenamiento seguro de campos "secretos" de la configuración.

Antes de este módulo, `ai_api_key`, `db_password` y `connection_string`
(que puede llevar embebida una contraseña) se guardaban en texto plano
en `settings.json`, en la carpeta de datos del usuario. Cualquier
persona o proceso con acceso de lectura a esa carpeta (otro usuario del
mismo equipo, malware, un backup mal configurado) podía leerlos
directamente con un editor de texto.

Ahora esos campos viven en el llavero nativo del sistema operativo:

    - Windows -> Windows Credential Manager (cifrado con DPAPI, ligado
      al usuario de Windows que inició sesión)
    - macOS   -> Keychain
    - Linux   -> Secret Service (GNOME Keyring / KWallet), si está
      disponible

`config/app_config.py` es el único módulo que debe importar este
archivo: el resto de la aplicación sigue leyendo
`AppConfig().settings.ai_api_key` como siempre, sin enterarse de dónde
vive el valor realmente.

DEGRADACIÓN CONTROLADA: si `keyring` no está instalado, o no hay
ningún backend de llavero disponible (típico en un servidor Linux sin
entorno gráfico), se degrada a leer/escribir en el propio
`settings.json` en texto plano — igual que el comportamiento anterior
— en vez de romper la aplicación. Se registra un aviso en el logger
para que quede visible que esta instalación no tiene cifrado real de
credenciales.
"""
from typing import Optional

from core.app_logger import get_logger

_KEYRING_SERVICE_NAME = "AsistenteIA-LaVianda"

SECRET_FIELDS = ("ai_api_key", "db_password", "connection_string")

_keyring_module = None
_keyring_available: Optional[bool] = None  # None = todavía no se probó


def _get_keyring():
    """Import perezoso + detección de disponibilidad real (una sola vez)."""
    global _keyring_module, _keyring_available
    if _keyring_available is not None:
        return _keyring_module if _keyring_available else None

    try:
        import keyring
        import keyring.errors

        # get_keyring() puede devolver un backend "fail" (Keyring no
        # configurado) en vez de lanzar una excepción; hay que probarlo
        # con una operación real para saberlo con certeza.
        keyring.get_password(_KEYRING_SERVICE_NAME, "__availability_probe__")
        _keyring_module = keyring
        _keyring_available = True
    except Exception as exc:  # noqa: BLE001 - cualquier fallo aquí = sin llavero disponible
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
    """True si hay un llavero real del SO disponible (no el respaldo en texto plano)."""
    return _get_keyring() is not None


def get_secret(field: str) -> str:
    """Lee un campo secreto del llavero del SO. Cadena vacía si no existe o no hay llavero."""
    keyring = _get_keyring()
    if keyring is None:
        return ""
    try:
        return keyring.get_password(_KEYRING_SERVICE_NAME, field) or ""
    except Exception as exc:  # noqa: BLE001
        get_logger().error("No se pudo leer '%s' del llavero seguro: %s", field, exc)
        return ""


def set_secret(field: str, value: str) -> bool:
    """
    Guarda (o borra, si `value` es vacío) un campo secreto en el
    llavero del SO. Retorna True si se pudo usar el llavero real,
    False si no hay backend disponible (el llamador debe decidir el
    respaldo en texto plano en ese caso).
    """
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
                pass  # ya no había nada guardado: no es un error
        return True
    except Exception as exc:  # noqa: BLE001
        get_logger().error("No se pudo guardar '%s' en el llavero seguro: %s", field, exc)
        return False
