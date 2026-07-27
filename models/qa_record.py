from dataclasses import dataclass


@dataclass
class QARecord:

    id: int
    question: str
    answer: str
    engine: str
    source_filenames: str
    created_at: str
