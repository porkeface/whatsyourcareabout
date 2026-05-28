from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import Item

DB_PATH = "data/wyca.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    domain TEXT NOT NULL,
    score REAL DEFAULT 0,
    raw_text TEXT,
    lang TEXT DEFAULT 'en',
    summary TEXT,
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    rendered_md TEXT,
    rendered_html TEXT,
    item_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_items_collected ON items(collected_at);
CREATE INDEX IF NOT EXISTS idx_items_domain ON items(domain);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.close()


def insert_item(item: Item, conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            """INSERT OR IGNORE INTO items
               (url, title, source, domain, score, raw_text, summary, lang, published_at, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.url, item.title, item.source, item.domain,
                item.score, item.raw_text, item.summary, item.lang,
                item.published_at, item.collected_at,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def insert_items(items: list[Item], conn: sqlite3.Connection) -> int:
    count = 0
    for item in items:
        if insert_item(item, conn):
            count += 1
    return count


def get_items_since(since: datetime, conn: sqlite3.Connection) -> list[Item]:
    cursor = conn.execute(
        "SELECT * FROM items WHERE collected_at >= ? ORDER BY score DESC",
        (since.isoformat(),),
    )
    rows = cursor.fetchall()
    return [
        Item(
            title=row["title"],
            url=row["url"],
            source=row["source"],
            domain=row["domain"],
            score=row["score"],
            raw_text=row["raw_text"] or "",
            summary=row["summary"] or "",
            lang=row["lang"],
            published_at=row["published_at"],
            collected_at=row["collected_at"],
        )
        for row in rows
    ]


def get_recent_items(hours: int = 24, conn: sqlite3.Connection | None = None) -> list[Item]:
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        return get_items_since(since, conn)
    finally:
        if own_conn:
            conn.close()
