from dataclasses import dataclass


@dataclass
class TrainingFile:

    id: int
    filename: str
    file_type: str
    size_bytes: int
    content_preview: str
    uploaded_at: str
    source_path: str = ""
    source_mtime: float = 0.0

    @property
    def is_from_training_folder(self) -> bool:
        return bool(self.source_path)
