"""Modelo de datos: información de una versión disponible en el servidor."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UpdateInfo:
    """
    Información de una versión publicada, tal como la devuelve el
    endpoint de actualizaciones (propio o de GitHub Releases).
    """

    version: str
    build: int
    download_url: str
    release_notes: List[str] = field(default_factory=list)
    published: str = ""
    mandatory: bool = False
    checksum_sha256: Optional[str] = None      # None si el servidor no lo publica todavía
    signature: Optional[str] = None             # firma digital del instalador, si existe
    min_supported_version: Optional[str] = None  # para forzar actualización si se queda muy atrás
