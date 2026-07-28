from collections import Counter
from typing import List, Tuple

from database.knowledge_store import KnowledgeStore
from models.qa_record import QARecord

OUT_OF_SCOPE_ENGINE = "Fuera de alcance"


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

    def top_unanswered_questions(self, limit: int = 10) -> List[Tuple[str, int]]:
        """
        Agrupa las preguntas que se respondieron con "no tengo esa
        información en la Base de Conocimiento" (ver
        ui/main_window._refuse_out_of_scope) y devuelve las más
        frecuentes, para que el equipo sepa qué documentos priorizar
        agregar a la carpeta Training — sin esto, ese dato quedaba
        guardado pero invisible.
        """
        records = self._store.list_qa_by_engine(OUT_OF_SCOPE_ENGINE, limit=500)
        normalized_counts = Counter(record.question.strip().lower() for record in records)
        return normalized_counts.most_common(limit)
