"""
Acceso a datos: SQL Server (motor empresarial).

`connect()` intenta una conexión real:

    1. Si el paquete `pyodbc` está instalado, abre una conexión real
       (usando la cadena de conexión indicada, o construyéndola a
       partir de servidor/base/usuario/contraseña) con un timeout
       corto, y la cierra inmediatamente.
    2. Si `pyodbc` no está instalado (por ejemplo, en un entorno sin
       el driver ODBC de SQL Server), se hace una prueba de
       conectividad de red real (socket TCP al puerto 1433 del
       servidor) para al menos confirmar que el host es alcanzable,
       dejando claro en el mensaje que no se validó usuario/clave.

En ambos casos se retorna un mensaje de diagnóstico legible, nunca un
simple "conectado" simulado.
"""
import socket
from dataclasses import dataclass
from typing import Tuple

DEFAULT_SQL_SERVER_PORT = 1433
CONNECTION_TIMEOUT_SECONDS = 5


@dataclass
class SQLServerCredentials:
    """Parámetros de conexión a SQL Server."""

    server: str = ""
    database: str = ""
    user: str = ""
    password: str = ""
    connection_string: str = ""


class SQLServerDatabase:
    """Conexión a SQL Server, con prueba de conectividad real."""

    def __init__(self, credentials: SQLServerCredentials | None = None) -> None:
        self._credentials = credentials or SQLServerCredentials()
        self._connected = False

    def connect(self) -> Tuple[bool, str]:
        creds = self._credentials

        if not creds.connection_string.strip() and not creds.server.strip():
            self._connected = False
            return False, "Debes indicar un servidor o una cadena de conexión"

        try:
            import pyodbc  # type: ignore
        except ImportError:
            return self._fallback_socket_check(creds)

        conn_str = self._build_connection_string(creds)
        try:
            connection = pyodbc.connect(conn_str, timeout=CONNECTION_TIMEOUT_SECONDS)
            connection.close()
            self._connected = True
            return True, "Conectado correctamente"
        except pyodbc.Error as exc:  # type: ignore[attr-defined]
            self._connected = False
            return False, self._describe_pyodbc_error(exc)
        except Exception as exc:  # noqa: BLE001
            self._connected = False
            return False, str(exc)[:160]

    def _fallback_socket_check(self, creds: SQLServerCredentials) -> Tuple[bool, str]:
        """
        Sin pyodbc (o sin el driver ODBC instalado en el sistema) no se
        puede abrir una sesión SQL real. Como alternativa honesta, se
        valida que el host/puerto sean alcanzables por red.
        """
        host = creds.server.strip()
        if not host:
            self._connected = False
            return False, "pyodbc no está instalado y no hay servidor para probar la red"

        # Permite server:puerto explícito; si no, usa el puerto por defecto.
        if ":" in host:
            hostname, port_str = host.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = DEFAULT_SQL_SERVER_PORT
        else:
            hostname, port = host, DEFAULT_SQL_SERVER_PORT

        try:
            with socket.create_connection((hostname, port), timeout=CONNECTION_TIMEOUT_SECONDS):
                self._connected = True
                return True, (
                    f"Host {hostname}:{port} alcanzable. "
                    "(pyodbc no está instalado: no se validó usuario/contraseña, "
                    "solo conectividad de red)"
                )
        except (socket.timeout, TimeoutError):
            self._connected = False
            return False, f"Tiempo de espera agotado al conectar con {hostname}:{port}"
        except OSError as exc:
            self._connected = False
            return False, f"No se pudo alcanzar {hostname}:{port} ({exc.strerror or exc})"

    @staticmethod
    def _build_connection_string(creds: SQLServerCredentials) -> str:
        if creds.connection_string.strip():
            return creds.connection_string.strip()
        return (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={creds.server};DATABASE={creds.database};"
            f"UID={creds.user};PWD={creds.password};"
        )

    @staticmethod
    def _describe_pyodbc_error(exc: Exception) -> str:
        message = str(exc)
        if "Login failed" in message:
            return "Usuario o contraseña incorrectos"
        if "timeout" in message.lower():
            return "Tiempo de espera agotado al conectar"
        return message[:160]

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected
