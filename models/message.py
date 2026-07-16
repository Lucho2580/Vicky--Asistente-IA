"""
Modelo de datos: Mensaje de chat.

Representa un único mensaje dentro de una conversación, ya sea del
usuario o de la IA. Se mantiene como dataclass simple para que pueda
ser reutilizado tanto por la UI (renderizado de burbujas) como por la
futura capa de persistencia (SQLite / SQL Server).
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Sender(str, Enum):
    """Origen del mensaje dentro de la conversación."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Un mensaje individual de la conversación."""

    content: str
    sender: Sender
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M"))

    @property
    def is_user(self) -> bool:
        return self.sender == Sender.USER
