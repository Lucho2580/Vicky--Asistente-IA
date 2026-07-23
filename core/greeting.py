import getpass
from datetime import datetime
from typing import Optional


def get_current_username() -> str:
    """
    Usuario del sistema operativo (el que tiene la sesión de Windows
    abierta), no un usuario propio de la app — la app no tiene su
    propio sistema de login todavía.
    """
    try:
        username = getpass.getuser()
        return username.strip().capitalize() if username and username.strip() else "Usuario"
    except Exception:
        return "Usuario"


def get_time_based_salutation(now: Optional[datetime] = None) -> str:
    """Devuelve 'Buenos días' / 'Buenas tardes' / 'Buenas noches' según la hora."""
    now = now or datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "Buenos días"
    if 12 <= hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def build_greeting(username: Optional[str] = None, now: Optional[datetime] = None) -> str:
    """Ej.: 'Buenos días, Carlos 👋'"""
    username = username or get_current_username()
    salutation = get_time_based_salutation(now)
    return f"{salutation}, {username} 👋"
