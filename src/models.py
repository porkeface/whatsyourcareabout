from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    title: str
    url: str
    source: str
    domain: str  # ai, finance, academic, tech, general, social
    score: float = 0.0
    raw_text: str = ""
    summary: str = ""
    lang: str = "en"
    published_at: datetime | None = None
    collected_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def url_hash(self) -> str:
        import hashlib
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]


@dataclass
class DailyDigest:
    date: str  # YYYY-MM-DD
    items: list[Item] = field(default_factory=list)
    item_count: int = 0
