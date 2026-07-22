"""
Logging simple de la aplicación.

Guarda un archivo de log diario en la carpeta de logs del usuario
(ver core/paths.py). Pensado inicialmente para el sistema de
actualizaciones ("si falla internet, no mostrar errores molestos:
registrar en logs"), pero cualquier otro módulo puede usarlo con
`get_logger()`.
"""
import logging
from logging.handlers import TimedRotatingFileHandler

from core.paths import LOGS_DIR

_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("asistente_ia_la_vianda")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = TimedRotatingFileHandler(
            filename=LOGS_DIR / "app.log", when="midnight", backupCount=30, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _logger = logger
    return logger
