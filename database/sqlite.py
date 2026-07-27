from pathlib import Path


class SQLiteDatabase:

    def __init__(self, db_path: str = "config/la_vianda.db") -> None:
        self._db_path = Path(db_path)
        self._connected = False

    def connect(self) -> bool:
        self._connected = False
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected
