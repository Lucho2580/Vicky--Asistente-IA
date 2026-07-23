"""Modelo de datos: registro centralizado de una pregunta y su respuesta."""
from dataclasses import dataclass


@dataclass
class QARecord:
    """
    Una pregunta y su respuesta, centralizadas para poder consultarlas
    en el tiempo. Incluye qué motor de IA respondió y qué archivos de
    entrenamiento (si los hubo) se usaron como contexto.
    """

    id: int
    question: str
    answer: str
    engine: str              # "GitHub Copilot", "OpenAI", "Gemini", "Offline"...
    source_filenames: str    # nombres de archivos usados como contexto, separados por coma ("" si ninguno)
    created_at: str          # ISO 8601
