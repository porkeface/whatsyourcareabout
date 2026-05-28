"""FastAPI backend for WYCA daily digest API."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import load_config
from src.database import DB_PATH, get_connection, init_db

logger = logging.getLogger("wyca.web")

app = FastAPI(title="WYCA API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class ItemResponse(BaseModel):
    title: str
    url: str
    source: str
    domain: str
    score: float
    raw_text: str
    summary: str
    lang: str
    published_at: str | None
    collected_at: str | None


class DigestResponse(BaseModel):
    date: str
    item_count: int
    items: list[ItemResponse]
    source_count: int


class DigestSummary(BaseModel):
    date: str
    item_count: int


class PaginatedItems(BaseModel):
    items: list[ItemResponse]
    total: int


class HealthResponse(BaseModel):
    status: str
    db_exists: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_item(row: sqlite3.Row) -> ItemResponse:
    return ItemResponse(
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


def _items_for_date(conn: sqlite3.Connection, date: str) -> list[ItemResponse]:
    """Return all items whose collected_at date matches the given YYYY-MM-DD string."""
    cursor = conn.execute(
        """
        SELECT * FROM items
        WHERE date(collected_at) = ?
        ORDER BY score DESC
        """,
        (date,),
    )
    return [_row_to_item(row) for row in cursor.fetchall()]


def _source_count_for_date(conn: sqlite3.Connection, date: str) -> int:
    cursor = conn.execute(
        """
        SELECT COUNT(DISTINCT source) AS cnt FROM items
        WHERE date(collected_at) = ?
        """,
        (date,),
    )
    row = cursor.fetchone()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    logger.info("Database initialized on startup")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_path = Path(DB_PATH)
    return HealthResponse(status="ok", db_exists=db_path.exists())


@app.get("/api/digests", response_model=list[DigestSummary])
async def list_digests() -> list[DigestSummary]:
    """List available digest dates with item counts, newest first."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT date(collected_at) AS date, COUNT(*) AS item_count
            FROM items
            GROUP BY date(collected_at)
            ORDER BY date(collected_at) DESC
            """
        )
        return [
            DigestSummary(date=row["date"], item_count=row["item_count"])
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


@app.get("/api/digest/latest", response_model=DigestResponse)
async def latest_digest() -> DigestResponse:
    """Get the most recent day's digest."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT date(collected_at) AS date FROM items ORDER BY collected_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            # Return empty digest for today if no data exists yet
            from datetime import date as _date

            today = _date.today().isoformat()
            return DigestResponse(date=today, item_count=0, items=[], source_count=0)

        date = row["date"]
        items = _items_for_date(conn, date)
        source_count = _source_count_for_date(conn, date)
        return DigestResponse(
            date=date,
            item_count=len(items),
            items=items,
            source_count=source_count,
        )
    finally:
        conn.close()


@app.get("/api/digest/{date}", response_model=DigestResponse)
async def digest_by_date(date: str) -> DigestResponse:
    """Get the digest for a specific date (YYYY-MM-DD)."""
    conn = get_connection()
    try:
        items = _items_for_date(conn, date)
        source_count = _source_count_for_date(conn, date)
        return DigestResponse(
            date=date,
            item_count=len(items),
            items=items,
            source_count=source_count,
        )
    finally:
        conn.close()


@app.get("/api/items", response_model=PaginatedItems)
async def list_items(
    domain: str | None = Query(None, description="Filter by domain"),
    source: str | None = Query(None, description="Filter by source"),
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    date_from: str | None = Query(None, description="Start date range (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="End date range (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedItems:
    """Get items with optional filters and pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if domain:
        conditions.append("domain = ?")
        params.append(domain)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if date:
        conditions.append("date(collected_at) = ?")
        params.append(date)
    if date_from:
        conditions.append("date(collected_at) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date(collected_at) <= ?")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM items {where_clause}", params
        ).fetchone()["cnt"]

        cursor = conn.execute(
            f"SELECT * FROM items {where_clause} ORDER BY score DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        items = [_row_to_item(row) for row in cursor.fetchall()]
        return PaginatedItems(items=items, total=total)
    finally:
        conn.close()


@app.post("/api/collect")
async def trigger_collection() -> dict[str, str]:
    """Trigger a background collection run."""
    try:
        config = load_config()
    except FileNotFoundError:
        # Fall back to defaults if config is missing
        config = {"sources": {}, "output": {"output_dir": "./output", "formats": ["markdown"]}}

    async def _run() -> None:
        try:
            from src.main import run_daily_digest

            await run_daily_digest(config)
        except Exception:
            logger.error("Background collection failed", exc_info=True)

    asyncio.create_task(_run())
    return {"status": "started"}
