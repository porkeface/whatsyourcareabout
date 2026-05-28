from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.models import Item

logger = logging.getLogger(__name__)

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
    title_zh TEXT DEFAULT '',
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
CREATE INDEX IF NOT EXISTS idx_items_url ON items(url);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    # Migration: add title_zh column if missing
    try:
        conn.execute("ALTER TABLE items ADD COLUMN title_zh TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.close()


def insert_item(item: Item, conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            """INSERT OR IGNORE INTO items
               (url, title, source, domain, score, raw_text, summary, title_zh, lang, published_at, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.url, item.title, item.source, item.domain,
                item.score, item.raw_text, item.summary, item.title_zh, item.lang,
                item.published_at, item.collected_at,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def insert_items(items: list[Item], conn: sqlite3.Connection) -> int:
    count = 0
    for item in items:
        if insert_item(item, conn):
            count += 1
    conn.commit()
    return count


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse a SQLite timestamp string into a timezone-aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


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
            title_zh=row["title_zh"] or "",
            lang=row["lang"],
            published_at=_parse_timestamp(row["published_at"]),
            collected_at=_parse_timestamp(row["collected_at"]),
        )
        for row in rows
    ]


def get_recent_items(hours: int = 24, conn: sqlite3.Connection | None = None) -> list[Item]:
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        return get_items_since(since, conn)
    finally:
        if own_conn:
            conn.close()


def update_item_summary(url: str, summary: str, conn: sqlite3.Connection) -> bool:
    """Update the summary field for an item by URL. Returns True if updated."""
    try:
        cursor = conn.execute(
            "UPDATE items SET summary = ? WHERE url = ? AND (summary IS NULL OR summary = '')",
            (summary, url),
        )
        updated = cursor.rowcount > 0
        if updated:
            logger.debug("Persisted summary for %s", url)
        return updated
    except sqlite3.Error:
        logger.error("Failed to update summary for url=%s", url, exc_info=True)
        return False


def update_item_summary_and_title(url: str, summary: str, title_zh: str, conn: sqlite3.Connection) -> bool:
    """Update summary and title_zh for an item by URL. Returns True if updated.

    Updates when: summary is empty OR title_zh is empty (to allow re-translation).
    """
    try:
        cursor = conn.execute(
            "UPDATE items SET summary = ?, title_zh = ? WHERE url = ? "
            "AND (summary IS NULL OR summary = '' OR title_zh IS NULL OR title_zh = '')",
            (summary, title_zh, url),
        )
        updated = cursor.rowcount > 0
        if updated:
            logger.debug("Persisted summary+title_zh for %s", url)
        return updated
    except sqlite3.Error:
        logger.error("Failed to update summary+title_zh for url=%s", url, exc_info=True)
        return False


def get_items_needing_summary(conn: sqlite3.Connection) -> list[str]:
    """Get URLs of items that have no summary yet. Returns list of URLs."""
    try:
        cursor = conn.execute(
            "SELECT url FROM items WHERE summary IS NULL OR summary = ''"
        )
        rows = cursor.fetchall()
        return [row["url"] for row in rows]
    except sqlite3.Error:
        logger.error("Failed to fetch items needing summary", exc_info=True)
        return []


def get_summary_by_url(url: str, conn: sqlite3.Connection) -> str | None:
    """Get cached summary for a URL. Returns None if not found."""
    try:
        cursor = conn.execute(
            "SELECT summary FROM items WHERE url = ? AND summary IS NOT NULL AND summary != ''",
            (url,),
        )
        row = cursor.fetchone()
        return row["summary"] if row else None
    except sqlite3.Error:
        logger.error("Failed to get summary for url=%s", url, exc_info=True)
        return None


def get_summaries_by_urls(urls: list[str], conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    """Bulk-fetch summaries for a list of URLs. Returns url->{summary, title_zh} mapping."""
    if not urls:
        return {}
    try:
        placeholders = ",".join("?" for _ in urls)
        cursor = conn.execute(
            f"SELECT url, summary, title_zh FROM items WHERE url IN ({placeholders}) "
            "AND summary IS NOT NULL AND summary != ''",
            urls,
        )
        return {
            row["url"]: {"summary": row["summary"], "title_zh": row["title_zh"] or ""}
            for row in cursor.fetchall()
        }
    except sqlite3.Error:
        logger.error("Failed to bulk-fetch summaries", exc_info=True)
        return {}
