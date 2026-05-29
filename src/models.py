from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Item:
    title: str
    url: str
    source: str
    domain: str  # ai, finance, academic, tech, general, social
    score: float = 0.0
    raw_text: str = ""
    summary: str = ""
    summary_zh: str = ""
    title_zh: str = ""
    lang: str = "en"
    published_at: datetime | None = None
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    url_hash: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Compute url_hash once and store it (frozen dataclass uses object.__setattr__)
        object.__setattr__(self, "url_hash", hashlib.sha256(self.url.encode()).hexdigest()[:16])


@dataclass
class DailyDigest:
    date: str  # YYYY-MM-DD
    items: list[Item] = field(default_factory=list)
    item_count: int = 0
