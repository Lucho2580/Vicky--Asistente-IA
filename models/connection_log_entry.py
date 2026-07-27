from dataclasses import dataclass


@dataclass
class ConnectionLogEntry:

    id: int
    category: str
    target_name: str
    success: bool
    message: str
    created_at: str
