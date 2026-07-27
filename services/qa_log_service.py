from typing import List

from database.knowledge_store import KnowledgeStore
from models.qa_record import QARecord


class QALogService:

    def __init__(self, store: KnowledgeStore | None = None) -> None:
        self._store = store or KnowledgeStore()

    def log(self, question: str, answer: str, engine: str, source_filenames: str = "") -> QARecord:
        return self._store.log_qa(question, answer, engine, source_filenames)

    def list_recent(self, limit: int = 50) -> List[QARecord]:
        return self._store.list_recent_qa(limit=limit)

    def search(self, query: str, limit: int = 50) -> List[QARecord]:
        if not query.strip():
            return self.list_recent(limit=limit)
        return self._store.search_qa(query, limit=limit)
