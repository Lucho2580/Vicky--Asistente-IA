from typing import List, Optional

from database.knowledge_store import KnowledgeStore
from models.connection_log_entry import ConnectionLogEntry

CATEGORY_AI = "ia"
CATEGORY_DATABASE = "base_de_datos"


class ConnectionLogService:

    def __init__(self, store: KnowledgeStore | None = None) -> None:
        self._store = store or KnowledgeStore()

    def log_ai_attempt(self, engine_name: str, success: bool, message: str) -> ConnectionLogEntry:
        return self._store.log_connection_attempt(CATEGORY_AI, engine_name, success, message)

    def log_database_attempt(self, target_name: str, success: bool, message: str) -> ConnectionLogEntry:
        return self._store.log_connection_attempt(CATEGORY_DATABASE, target_name, success, message)

    def list_recent(self, category: Optional[str] = None, limit: int = 20) -> List[ConnectionLogEntry]:
        return self._store.list_recent_connections(category=category, limit=limit)
