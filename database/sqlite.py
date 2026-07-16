"""
Acceso a datos: SQLite (motor local, sin dependencias externas).

Preparado para almacenar historial de conversaciones en desarrollo o
en instalaciones sin SQL Server disponible. Sin lógica de negocio
todavía: solo el contrato de conexión.
"""
from pathlib import Path


class SQLiteDatabase:
    """Conexión (pendiente de implementar) a una base de datos SQLite local."""

    def __init__(self, db_path: str = "config/la_vianda.db") -> None:
        self._db_path = Path(db_path)
        self._connected = False

    def connect(self) -> bool:
        # TODO: abrir conexión real con sqlite3 y crear el esquema si no existe.
        self._connected = False
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected
