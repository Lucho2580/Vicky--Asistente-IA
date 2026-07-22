"""
Capa de persistencia de conversaciones (SQLite).

Almacena todas las conversaciones y mensajes en un archivo
`conversations.db` independiente de cualquier otra base de datos que
la aplicación pueda usar a futuro (SQL Server, etc.). Esta clase es la
ÚNICA que conoce SQL/SQLite; el resto de la aplicación interactúa
siempre a través de `services.conversation_service.ConversationService`.

Tablas:
    conversations(id, title, created_at)
    messages(id, conversation_id, role, content, timestamp)
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from core.paths import CONVERSATIONS_DB_PATH
from models.conversation import Conversation
from models.message import Message, Sender

DB_PATH = CONVERSATIONS_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL DEFAULT 'Nueva conversación',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id);
"""


class ConversationStore:
    """Acceso de bajo nivel (CRUD) a conversations.db."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON;")
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    # ------------------------------------------------------------------ #
    # Conversaciones
    # ------------------------------------------------------------------ #
    def create_conversation(self, title: str = "Nueva conversación") -> Conversation:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self._connection.execute(
            "INSERT INTO conversations (title, created_at) VALUES (?, ?)",
            (title, now),
        )
        self._connection.commit()
        return Conversation(id=cursor.lastrowid, title=title, created_at=now, message_count=0)

    def update_title(self, conversation_id: int, title: str) -> None:
        self._connection.execute(
            "UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id)
        )
        self._connection.commit()

    def get_all_conversations(self) -> List[Conversation]:
        rows = self._connection.execute(
            """
            SELECT c.id, c.title, c.created_at, COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
        return [
            Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                message_count=row["message_count"],
            )
            for row in rows
        ]

    def get_conversation(self, conversation_id: int) -> Conversation | None:
        row = self._connection.execute(
            """
            SELECT c.id, c.title, c.created_at, COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return Conversation(
            id=row["id"], title=row["title"], created_at=row["created_at"], message_count=row["message_count"]
        )

    def delete_conversation(self, conversation_id: int) -> None:
        """Elimina la conversación; sus mensajes se borran solos (ON DELETE CASCADE)."""
        self._connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self._connection.commit()

    # ------------------------------------------------------------------ #
    # Mensajes
    # ------------------------------------------------------------------ #
    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        now = datetime.now().isoformat(timespec="seconds")
        self._connection.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        self._connection.commit()
        return Message(content=content, sender=Sender(role), timestamp=_extract_time(now))

    def get_messages(self, conversation_id: int) -> List[Message]:
        rows = self._connection.execute(
            "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC, id ASC",
            (conversation_id,),
        ).fetchall()
        return [
            Message(content=row["content"], sender=Sender(row["role"]), timestamp=_extract_time(row["timestamp"]))
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()


def _extract_time(iso_timestamp: str) -> str:
    """Extrae HH:MM de un timestamp ISO completo, para mostrar en las burbujas."""
    try:
        return datetime.fromisoformat(iso_timestamp).strftime("%H:%M")
    except ValueError:
        return iso_timestamp
