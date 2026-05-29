"""FastAPI backend for WYCA daily digest API."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import load_config
from src.database import DB_PATH, get_connection, init_db

logger = logging.getLogger("wyca.web")

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------

_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 10  # max requests per window per IP


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > cutoff]
    if len(_rate_store[ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")
    _rate_store[ip].append(now)


# ---------------------------------------------------------------------------
# API key authentication for write endpoints
# ---------------------------------------------------------------------------

_COLLECT_API_KEY = os.environ.get("WYCA_COLLECT_API_KEY", "")


def _verify_collect_key(request: Request) -> None:
    """Verify API key for the /api/collect endpoint."""
    if not _COLLECT_API_KEY:
        return  # No key configured — allow open access (dev mode)
    auth = request.headers.get("X-API-Key", "")
    if auth != _COLLECT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized on startup")
    yield


app = FastAPI(title="WYCA API", version="0.1.0", lifespan=lifespan)

# CORS: restrict to known origins in production
_allowed_origins = os.environ.get(
    "WYCA_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class ItemResponse(BaseModel):
    title: str
    title_zh: str
    url: str
    source: str
    domain: str
    score: float
    raw_text: str
    summary: str
    summary_zh: str
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
        title_zh=row["title_zh"] or "",
        url=row["url"],
        source=row["source"],
        domain=row["domain"],
        score=row["score"],
        raw_text=row["raw_text"] or "",
        summary=row["summary"] or "",
        summary_zh=row["summary_zh"] or "",
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
# Background task tracking
# ---------------------------------------------------------------------------

_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    _background_tasks.discard(task)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(date_str: str) -> str:
    """Validate a date string is in YYYY-MM-DD format."""
    if not _DATE_RE.match(date_str):
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")
    return date_str


async def _run_db(func, *args):
    """Run a synchronous DB function off the event loop."""
    return await asyncio.to_thread(func, *args)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_path = Path(DB_PATH)
    return HealthResponse(status="ok", db_exists=db_path.exists())


@app.get("/api/digests", response_model=list[DigestSummary])
async def list_digests(request: Request) -> list[DigestSummary]:
    """List available digest dates with item counts, newest first."""
    _check_rate_limit(request.client.host if request.client else "unknown")

    def _query():
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

    return await _run_db(_query)


@app.get("/api/digest/latest", response_model=DigestResponse)
async def latest_digest(request: Request) -> DigestResponse:
    """Get the most recent day's digest."""
    _check_rate_limit(request.client.host if request.client else "unknown")

    def _query():
        conn = get_connection()
        try:
            cursor = conn.execute(
                "SELECT date(collected_at) AS date FROM items ORDER BY collected_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                from datetime import date as _date
                today = _date.today().isoformat()
                return DigestResponse(date=today, item_count=0, items=[], source_count=0)

            date_val = row["date"]
            items = _items_for_date(conn, date_val)
            source_count = _source_count_for_date(conn, date_val)
            return DigestResponse(
                date=date_val,
                item_count=len(items),
                items=items,
                source_count=source_count,
            )
        finally:
            conn.close()

    return await _run_db(_query)


@app.get("/api/digest/{date}", response_model=DigestResponse)
async def digest_by_date(date: str, request: Request) -> DigestResponse:
    """Get the digest for a specific date (YYYY-MM-DD)."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    _validate_date(date)

    def _query():
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

    return await _run_db(_query)


@app.get("/api/items", response_model=PaginatedItems)
async def list_items(
    request: Request,
    domain: str | None = Query(None, description="Filter by domain"),
    source: str | None = Query(None, description="Filter by source"),
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
    date_from: str | None = Query(None, description="Start date range (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="End date range (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PaginatedItems:
    """Get items with optional filters and pagination."""
    _check_rate_limit(request.client.host if request.client else "unknown")

    if date:
        _validate_date(date)
    if date_from:
        _validate_date(date_from)
    if date_to:
        _validate_date(date_to)

    def _query():
        conditions: list[str] = []
        params: list[Any] = []

        ALLOWED_COLUMNS = {"domain", "source"}

        if domain:
            if domain not in ALLOWED_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid domain filter: {domain}")
            conditions.append("domain = ?")
            params.append(domain)
        if source:
            if source not in ALLOWED_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid source filter: {source}")
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

    return await _run_db(_query)


@app.post("/api/collect")
async def trigger_collection(request: Request) -> dict[str, str]:
    """Trigger a background collection run."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    _verify_collect_key(request)

    try:
        config = load_config()
    except FileNotFoundError:
        config = {"sources": {}, "output": {"output_dir": "./output", "formats": ["markdown"]}}

    async def _run() -> None:
        try:
            from src.main import run_daily_digest
            await run_daily_digest(config)
        except Exception:
            logger.error("Background collection failed", exc_info=True)

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_track_task)
    return {"status": "started"}
