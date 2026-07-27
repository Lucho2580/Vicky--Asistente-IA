from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Sender(str, Enum):

    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:

    content: str
    sender: Sender
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M"))

    @property
    def is_user(self) -> bool:
        return self.sender == Sender.USER
