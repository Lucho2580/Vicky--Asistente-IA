"""
Servicio de Base de Conocimiento.

Gestiona los archivos de "entrenamiento" (documentos que sirven de
contexto para las respuestas de la IA): subirlos, listarlos, buscarlos
y eliminarlos. Toda la persistencia real vive en `KnowledgeStore`
(SQLite); este servicio agrega la lógica de negocio (extracción de
texto, validación de tipos de archivo, extracción de palabras clave,
armado de contexto para el prompt).
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

from core.paths import TRAINING_DIR
from database.knowledge_store import KnowledgeStore
from models.training_file import TrainingFile

# Tipos de archivo de los que se puede extraer texto de forma directa.
# (PDF/DOCX quedan para una futura iteración: requieren librerías de
# parseo adicionales que no están en el alcance actual.)
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}

MAX_CONTENT_LENGTH = 200_000  # ~200 KB de texto por archivo, para no inflar la BD
MIN_KEYWORD_LENGTH = 3

# Palabras muy comunes que no aportan a la búsqueda (se ignoran al
# extraer palabras clave de la pregunta del usuario).
_STOPWORDS = {
    "que", "cual", "cuales", "cuál", "cuáles", "es", "la", "el", "los", "las",
    "de", "del", "en", "y", "o", "un", "una", "unos", "unas", "para", "por",
    "con", "sin", "se", "su", "sus", "al", "lo", "le", "les", "mi", "mis",
    "tu", "tus", "como", "cómo", "cuando", "cuándo", "donde", "dónde", "qué",
    "the", "is", "are", "of", "to", "for", "in", "on", "and", "or", "a", "an",
}


class UnsupportedFileTypeError(Exception):
    """Se lanza cuando el archivo no es un tipo de texto soportado todavía."""


def extract_keywords(text: str) -> List[str]:
    """Extrae palabras clave relevantes de una pregunta (sin stopwords ni signos)."""
    words = re.findall(r"[\wáéíóúñü]+", text.lower(), flags=re.UNICODE)
    return [w for w in words if len(w) >= MIN_KEYWORD_LENGTH and w not in _STOPWORDS]


def friendly_name(filename: str) -> str:
    """Convierte 'cambiar_contrasena_zeus.md' en 'Cambiar contrasena zeus', para mostrar en la UI."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    words = stem.replace("_", " ").replace("-", " ").split()
    return " ".join(w.capitalize() for w in words) if words else stem


class KnowledgeBase:
    """Punto único de acceso a la Base de Conocimiento (documentos de entrenamiento)."""

    def __init__(self, store: Optional[KnowledgeStore] = None) -> None:
        self._store = store or KnowledgeStore()

    def add_document(self, file_path: str) -> TrainingFile:
        """
        Sube un archivo real de disco a la Base de Conocimiento: lee su
        contenido de texto y lo persiste en knowledge.db.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

        extension = path.suffix.lower()
        if extension not in SUPPORTED_TEXT_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_TEXT_EXTENSIONS))
            raise UnsupportedFileTypeError(
                f"Tipo de archivo '{extension or 'sin extensión'}' no soportado todavía. "
                f"Por ahora se aceptan: {supported} (PDF/Word quedan para una próxima iteración)."
            )

        content = path.read_text(encoding="utf-8", errors="replace")[:MAX_CONTENT_LENGTH]
        size_bytes = path.stat().st_size

        return self._store.add_training_file(
            filename=path.name,
            file_type=extension.lstrip("."),
            size_bytes=size_bytes,
            content_text=content,
        )

    def list_documents(self) -> List[TrainingFile]:
        return self._store.list_training_files()

    # ------------------------------------------------------------------ #
    # Sincronización con la carpeta "Training" (sin subida manual)
    # ------------------------------------------------------------------ #
    def sync_training_folder(self, folder_path: Optional[Path] = None) -> Dict[str, object]:
        """
        Sincroniza los archivos de la carpeta "Training" con la Base de
        Conocimiento: el usuario solo tiene que colocar sus archivos ahí
        (por ejemplo, arrastrándolos desde el Explorador de Windows), sin
        tener que subirlos uno por uno desde la app.

        - Archivo nuevo en la carpeta -> se agrega.
        - Archivo ya indexado pero modificado (fecha de modificación más
          reciente que la registrada) -> se re-indexa con el contenido
          actualizado.
        - Archivo que ya no está en la carpeta -> se elimina de la Base
          de Conocimiento.
        - Los archivos subidos manualmente (chat o botón "Subir archivo")
          NO se tocan: solo se gestionan los que tienen un `source_path`
          registrado (es decir, los que vinieron de esta carpeta).

        Retorna un resumen: {"added": n, "updated": n, "removed": n, "errors": [...]}
        """
        folder = Path(folder_path) if folder_path else TRAINING_DIR
        folder.mkdir(parents=True, exist_ok=True)

        summary: Dict[str, object] = {"added": 0, "updated": 0, "removed": 0, "errors": []}

        disk_files = {
            str(p.resolve()): p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS
        }

        tracked_by_path = {doc.source_path: doc for doc in self._store.list_training_files_from_folder()}

        for path_str, path_obj in disk_files.items():
            try:
                mtime = path_obj.stat().st_mtime
                existing = tracked_by_path.get(path_str)
                if existing is None:
                    self._add_from_training_folder(path_obj, mtime)
                    summary["added"] += 1
                elif mtime > existing.source_mtime:
                    self._store.remove_training_file(existing.id)
                    self._add_from_training_folder(path_obj, mtime)
                    summary["updated"] += 1
            except Exception as exc:  # noqa: BLE001 - un archivo problemático no debe frenar el resto
                summary["errors"].append(f"{path_obj.name}: {exc}")

        for path_str, existing in tracked_by_path.items():
            if path_str not in disk_files:
                self._store.remove_training_file(existing.id)
                summary["removed"] += 1

        return summary

    def _add_from_training_folder(self, path: Path, mtime: float) -> TrainingFile:
        content = path.read_text(encoding="utf-8", errors="replace")[:MAX_CONTENT_LENGTH]
        size_bytes = path.stat().st_size
        return self._store.add_training_file(
            filename=path.name,
            file_type=path.suffix.lstrip(".").lower(),
            size_bytes=size_bytes,
            content_text=content,
            source_path=str(path.resolve()),
            source_mtime=mtime,
        )

    def search(self, query: str, top_k: int = 5) -> List[TrainingFile]:
        """
        Busca documentos relevantes para `query` (una pregunta completa
        del usuario). Extrae las palabras clave de la pregunta y busca
        coincidencias reales de esas palabras en los documentos —
        comparar la pregunta completa como una sola cadena nunca
        encontraría nada, porque los documentos no contienen la
        pregunta textual.
        """
        return [doc for _score, doc in self.search_with_scores(query, top_k=top_k)]

    def search_with_scores(self, query: str, top_k: int = 5) -> List[tuple]:
        """Igual que `search`, pero devuelve tuplas (puntaje, TrainingFile)."""
        keywords = extract_keywords(query)
        if not keywords:
            return []
        return self._store.search_training_files_scored(keywords, top_k=top_k)

    def detect_ambiguous_matches(self, query: str, top_k: int = 5) -> List[TrainingFile]:
        """
        Si dos o más documentos empatan (o casi empatan) en el primer
        lugar de relevancia, la pregunta es ambigua: no hay un
        procedimiento claramente más aplicable que otro (ej. "cambiar
        la contraseña" podría ser la del correo o la de Zeus). En ese
        caso, en vez de mezclar el contexto de ambos o elegir uno al
        azar, conviene preguntarle al usuario a cuál se refiere.

        Como el puntaje es un valor ponderado (no un conteo entero), se
        considera "empate" cuando el segundo lugar queda dentro de un
        15% del puntaje del primero, en vez de exigir una igualdad
        exacta (que casi nunca ocurriría con valores decimales).

        Retorna la lista de documentos empatados en el primer lugar
        (2 o más) si la pregunta es ambigua, o una lista vacía si hay
        un único ganador claro (o ninguna coincidencia).
        """
        scored = self.search_with_scores(query, top_k=top_k)
        if len(scored) < 2:
            return []

        top_score = scored[0][0]
        threshold = top_score * 0.85
        tied = [doc for score, doc in scored if score >= threshold]

        return tied if len(tied) >= 2 else []

    def remove_document(self, document_id: int) -> None:
        self._store.remove_training_file(document_id)

    def update_document(self, document_id: int, filename: Optional[str] = None) -> None:
        self._store.update_training_file(document_id, filename=filename)

    def build_context_snippet(self, matches: List[TrainingFile], max_chars_per_doc: int = 800) -> str:
        """
        Arma un bloque de texto con el contenido de los documentos
        encontrados, listo para inyectarse como contexto en el prompt
        que se envía al modelo de IA (patrón RAG simple).
        """
        if not matches:
            return ""

        blocks = []
        for doc in matches:
            full_content = self._store.get_training_file_content(doc.id) or doc.content_preview
            blocks.append(f"--- {doc.filename} ---\n{full_content[:max_chars_per_doc]}")

        return "\n\n".join(blocks)
