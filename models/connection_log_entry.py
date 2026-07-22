"""Modelo de datos: un intento de conexión (IA o Base de Datos), para historial."""
from dataclasses import dataclass


@dataclass
class ConnectionLogEntry:
    """Registro histórico de un intento de prueba de conexión."""

    id: int
    category: str      # "ia" | "base_de_datos"
    target_name: str   # nombre del motor ("OpenAI", "GitHub Copilot") o servidor de BD
    success: bool
    message: str        # detalle real devuelto por el proveedor/servidor
    created_at: str     # ISO 8601
