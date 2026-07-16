"""Modelo de datos: Conversación (resumen para historial)."""
from dataclasses import dataclass


@dataclass
class Conversation:
    """Resumen de una conversación, usado en el historial y como estado activo."""

    id: int
    title: str
    created_at: str      # ISO 8601, ej. "2026-07-16T09:45:00"
    message_count: int = 0
