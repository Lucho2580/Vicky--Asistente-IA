"""
Comparación de versiones semánticas (major.minor.patch).

Importante: NO se puede comparar como texto ("1.10.0" > "1.9.0" es
falso si se compara como string, porque "1" < "9" carácter a
carácter) — hay que parsear cada parte como número.
"""
import re
from typing import Tuple

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_version(version_string: str) -> Tuple[int, int, int]:
    """
    Convierte "1.3.2" (o "v1.3.2") en (1, 3, 2). Si el string no tiene
    el formato esperado, devuelve (0, 0, 0) en vez de lanzar una
    excepción — una respuesta de servidor mal formada no debería
    tirar abajo la verificación de actualizaciones.
    """
    match = _VERSION_RE.match(version_string.strip())
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def compare_versions(version_a: str, version_b: str) -> int:
    """
    Compara dos versiones semánticas.

    Retorna:
        -1 si version_a < version_b
         0 si son iguales
         1 si version_a > version_b
    """
    parsed_a = parse_version(version_a)
    parsed_b = parse_version(version_b)
    if parsed_a < parsed_b:
        return -1
    if parsed_a > parsed_b:
        return 1
    return 0


def is_newer(candidate_version: str, current_version: str) -> bool:
    """True si `candidate_version` es estrictamente más nueva que `current_version`."""
    return compare_versions(candidate_version, current_version) > 0
