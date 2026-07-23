"""Modelo de datos: archivo subido a la Base de Conocimiento (entrenamiento)."""
from dataclasses import dataclass


@dataclass
class TrainingFile:
    """Un archivo subido para servir de contexto/entrenamiento a la IA."""

    id: int
    filename: str
    file_type: str          # extensión, ej. "txt", "csv", "md"
    size_bytes: int
    content_preview: str    # primeros ~200 caracteres, para mostrar en listas
    uploaded_at: str        # ISO 8601
    # Si el archivo proviene de la carpeta "Training" (sincronización
    # automática), source_path tiene la ruta original en disco y
    # source_mtime su fecha de modificación (para detectar cambios).
    # Si se subió manualmente (chat o botón "Subir archivo"), ambos
    # quedan vacíos/0 y la app no lo gestiona automáticamente.
    source_path: str = ""
    source_mtime: float = 0.0

    @property
    def is_from_training_folder(self) -> bool:
        return bool(self.source_path)
