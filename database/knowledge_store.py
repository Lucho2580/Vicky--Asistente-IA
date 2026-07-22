"""
Capa de persistencia de la Base de Conocimiento (SQLite).

Almacena, en un archivo `knowledge.db` independiente de
`conversations.db`:

    training_files      -> archivos subidos para servir de contexto/entrenamiento
    qa_log              -> cada pregunta y respuesta, centralizada
    connection_log      -> historial de cada intento de conexión (IA/BD)

Esta es la ÚNICA clase que conoce SQL/SQLite para estos datos; el
resto de la aplicación interactúa a través de los servicios en
`services/`.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.paths import KNOWLEDGE_DB_PATH
from models.connection_log_entry import ConnectionLogEntry
from models.qa_record import QARecord
from models.training_file import TrainingFile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS training_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    content_text    TEXT NOT NULL,
    uploaded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    question         TEXT NOT NULL,
    answer            TEXT NOT NULL,
    engine            TEXT NOT NULL,
    source_filenames  TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connection_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT NOT NULL CHECK (category IN ('ia', 'base_de_datos')),
    target_name  TEXT NOT NULL,
    success      INTEGER NOT NULL,
    message      TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qa_log_created_at ON qa_log (created_at);
CREATE INDEX IF NOT EXISTS idx_connection_log_created_at ON connection_log (created_at);
"""

PREVIEW_LENGTH = 200

_TRAINING_FILES_COLUMNS = (
    "id, filename, file_type, size_bytes, content_text, uploaded_at, source_path, source_mtime"
)


class KnowledgeStore:
    """Acceso de bajo nivel (CRUD) a knowledge.db."""

    def __init__(self, db_path: Path = KNOWLEDGE_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(_SCHEMA)
        self._connection.commit()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """
        Agrega columnas nuevas a bases de datos ya existentes (creadas
        antes de que existiera la sincronización con la carpeta
        Training). `CREATE TABLE IF NOT EXISTS` no modifica una tabla
        que ya existe, así que hace falta este paso aparte.
        """
        existing_columns = {
            row["name"] for row in self._connection.execute("PRAGMA table_info(training_files)").fetchall()
        }
        if "source_path" not in existing_columns:
            self._connection.execute(
                "ALTER TABLE training_files ADD COLUMN source_path TEXT NOT NULL DEFAULT ''"
            )
        if "source_mtime" not in existing_columns:
            self._connection.execute(
                "ALTER TABLE training_files ADD COLUMN source_mtime REAL NOT NULL DEFAULT 0"
            )
        self._connection.commit()

    @staticmethod
    def _row_to_training_file(row: sqlite3.Row) -> TrainingFile:
        return TrainingFile(
            id=row["id"],
            filename=row["filename"],
            file_type=row["file_type"],
            size_bytes=row["size_bytes"],
            content_preview=row["content_text"][:PREVIEW_LENGTH],
            uploaded_at=row["uploaded_at"],
            source_path=row["source_path"] or "",
            source_mtime=row["source_mtime"] or 0.0,
        )

    # ------------------------------------------------------------------ #
    # training_files
    # ------------------------------------------------------------------ #
    def add_training_file(
        self,
        filename: str,
        file_type: str,
        size_bytes: int,
        content_text: str,
        source_path: str = "",
        source_mtime: float = 0.0,
    ) -> TrainingFile:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self._connection.execute(
            """
            INSERT INTO training_files
                (filename, file_type, size_bytes, content_text, uploaded_at, source_path, source_mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, file_type, size_bytes, content_text, now, source_path, source_mtime),
        )
        self._connection.commit()
        return TrainingFile(
            id=cursor.lastrowid,
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            content_preview=content_text[:PREVIEW_LENGTH],
            uploaded_at=now,
            source_path=source_path,
            source_mtime=source_mtime,
        )

    def list_training_files(self) -> List[TrainingFile]:
        rows = self._connection.execute(
            f"SELECT {_TRAINING_FILES_COLUMNS} FROM training_files ORDER BY uploaded_at DESC"
        ).fetchall()
        return [self._row_to_training_file(row) for row in rows]

    def list_training_files_from_folder(self) -> List[TrainingFile]:
        """Solo los archivos gestionados automáticamente por la carpeta Training."""
        rows = self._connection.execute(
            f"SELECT {_TRAINING_FILES_COLUMNS} FROM training_files WHERE source_path != '' "
            "ORDER BY filename ASC"
        ).fetchall()
        return [self._row_to_training_file(row) for row in rows]

    def search_training_files(self, keywords: List[str], top_k: int = 5) -> List[TrainingFile]:
        """
        Búsqueda por palabras clave con puntaje simple de relevancia:
        cada documento se puntúa por cuántas de las `keywords` aparecen
        en su contenido o nombre de archivo, y se devuelven los mejores
        `top_k`. Es una heurística simple (no embeddings/semántica),
        pero es una coincidencia real, no una comparación de la
        pregunta completa como una sola cadena (eso nunca encontraría
        nada, ya que los documentos no contienen la pregunta textual).
        """
        return [doc for _score, doc in self.search_training_files_scored(keywords, top_k=top_k)]

    def search_training_files_scored(self, keywords: List[str], top_k: int = 5) -> List[tuple]:
        """
        Igual que `search_training_files`, pero devuelve tuplas
        (puntaje, TrainingFile) en vez de solo los documentos. Se usa
        para detectar preguntas ambiguas: si los dos primeros resultados
        empatan en puntaje, no hay un único documento claramente más
        relevante y conviene preguntarle al usuario a cuál se refiere,
        en vez de adivinar o mezclar el contexto de ambos.

        El puntaje pondera cada palabra clave de forma inversa a en
        cuántos documentos aparece (similar a TF-IDF): una palabra que
        aparece en todos los documentos (ej. "contraseña" en varios
        procedimientos distintos) no debería ayudar a decidir cuál es
        el más relevante; una palabra que aparece en pocos documentos
        (ej. "zeus") sí debería pesar mucho más para esos documentos.
        Además se cuenta cuántas veces aparece cada palabra dentro del
        documento (no solo si aparece o no), para que un documento que
        trata el tema a fondo puntúe más que uno que solo lo menciona
        de pasada.
        """
        if not keywords:
            return []

        rows = self._connection.execute(
            f"SELECT {_TRAINING_FILES_COLUMNS} FROM training_files"
        ).fetchall()
        if not rows:
            return []

        combined_texts = [(row["content_text"] + " " + row["filename"]).lower() for row in rows]

        # Frecuencia de documentos que contienen cada palabra clave.
        doc_frequency = {
            kw: sum(1 for text in combined_texts if kw in text) for kw in keywords
        }

        scored: List[tuple] = []
        for row, combined in zip(rows, combined_texts):
            score = 0.0
            for kw in keywords:
                df = doc_frequency[kw]
                if df == 0:
                    continue
                occurrences = combined.count(kw)
                score += occurrences * (1.0 / df)
            if score > 0:
                scored.append((round(score, 4), row))

        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [(score, self._row_to_training_file(row)) for score, row in scored[:top_k]]

    def get_training_file_content(self, file_id: int) -> Optional[str]:
        row = self._connection.execute(
            "SELECT content_text FROM training_files WHERE id = ?", (file_id,)
        ).fetchone()
        return row["content_text"] if row else None

    def update_training_file(self, file_id: int, filename: Optional[str] = None) -> None:
        if filename is not None:
            self._connection.execute(
                "UPDATE training_files SET filename = ? WHERE id = ?", (filename, file_id)
            )
            self._connection.commit()

    def remove_training_file(self, file_id: int) -> None:
        self._connection.execute("DELETE FROM training_files WHERE id = ?", (file_id,))
        self._connection.commit()

    # ------------------------------------------------------------------ #
    # qa_log (preguntas y respuestas centralizadas)
    # ------------------------------------------------------------------ #
    def log_qa(self, question: str, answer: str, engine: str, source_filenames: str = "") -> QARecord:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self._connection.execute(
            """
            INSERT INTO qa_log (question, answer, engine, source_filenames, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (question, answer, engine, source_filenames, now),
        )
        self._connection.commit()
        return QARecord(
            id=cursor.lastrowid,
            question=question,
            answer=answer,
            engine=engine,
            source_filenames=source_filenames,
            created_at=now,
        )

    def list_recent_qa(self, limit: int = 50) -> List[QARecord]:
        rows = self._connection.execute(
            "SELECT * FROM qa_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [QARecord(**dict(row)) for row in rows]

    def search_qa(self, query: str, limit: int = 50) -> List[QARecord]:
        like_pattern = f"%{query.strip()}%"
        rows = self._connection.execute(
            """
            SELECT * FROM qa_log
            WHERE question LIKE ? OR answer LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (like_pattern, like_pattern, limit),
        ).fetchall()
        return [QARecord(**dict(row)) for row in rows]

    # ------------------------------------------------------------------ #
    # connection_log (historial de conexiones IA/BD)
    # ------------------------------------------------------------------ #
    def log_connection_attempt(
        self, category: str, target_name: str, success: bool, message: str
    ) -> ConnectionLogEntry:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self._connection.execute(
            """
            INSERT INTO connection_log (category, target_name, success, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (category, target_name, 1 if success else 0, message, now),
        )
        self._connection.commit()
        return ConnectionLogEntry(
            id=cursor.lastrowid,
            category=category,
            target_name=target_name,
            success=success,
            message=message,
            created_at=now,
        )

    def list_recent_connections(self, category: Optional[str] = None, limit: int = 20) -> List[ConnectionLogEntry]:
        if category:
            rows = self._connection.execute(
                "SELECT * FROM connection_log WHERE category = ? ORDER BY created_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM connection_log ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            ConnectionLogEntry(
                id=row["id"],
                category=row["category"],
                target_name=row["target_name"],
                success=bool(row["success"]),
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()
