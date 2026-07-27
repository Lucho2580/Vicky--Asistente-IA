from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UpdateInfo:

    version: str
    build: int
    download_url: str
    release_notes: List[str] = field(default_factory=list)
    published: str = ""
    mandatory: bool = False
    checksum_sha256: Optional[str] = None
    signature: Optional[str] = None
    min_supported_version: Optional[str] = None
