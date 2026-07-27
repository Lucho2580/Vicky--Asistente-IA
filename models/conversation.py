from dataclasses import dataclass


@dataclass
class Conversation:

    id: int
    title: str
    created_at: str
    message_count: int = 0
