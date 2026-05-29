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
from src.settings_db import (
    get_all_settings,
    get_effective_config,
    get_setting,
    init_settings_from_config,
    set_setting,
)

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
    # Initialize settings from config.yaml defaults
    try:
        config = load_config()
        init_settings_from_config(config)
        logger.info("Settings initialized from config")
    except Exception:
        logger.warning("Could not initialize settings from config", exc_info=True)
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
        config = get_effective_config()
    except Exception:
        logger.error("Failed to load effective config, falling back to defaults", exc_info=True)
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


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

# API key config mapping: env_key -> display name
_API_KEY_MAP = {
    "MIMO_API_KEY": "MIMO (AI 摘要)",
    "NEWSAPI_KEY": "NewsAPI",
    "FINNHUB_KEY": "Finnhub (金融)",
    "DAILYHOT_API_URL": "DailyHotApi (热搜聚合)",
    "HTTPS_PROXY": "代理地址",
    "TELEGRAM_BOT_TOKEN": "Telegram Bot Token",
    "TELEGRAM_CHAT_ID": "Telegram Chat ID",
}


def _mask_value(value: str) -> str:
    """Mask a sensitive value, showing first 3 and last 4 chars."""
    if not value or len(value) <= 7:
        return "***"
    return f"{value[:3]}{'*' * (len(value) - 7)}{value[-4:]}"


@app.get("/api/settings")
async def get_settings(request: Request) -> dict:
    """Get all runtime settings."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    return get_all_settings()


@app.put("/api/settings")
async def update_settings(request: Request, body: dict) -> dict[str, str]:
    """Batch update settings."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    for key, value in body.items():
        set_setting(key, value)
    return {"status": "updated"}


@app.get("/api/settings/sources")
async def get_sources(request: Request) -> dict:
    """Get all data sources with their configuration."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    sources = get_setting("sources", {})
    return {"sources": sources}


@app.put("/api/settings/sources/{name}")
async def update_source(name: str, request: Request, body: dict) -> dict[str, str]:
    """Update a single data source configuration."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    sources = get_setting("sources", {})
    if name not in sources:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")

    # Update allowed fields
    source = sources[name]
    for key in ("enabled", "weight", "max_items"):
        if key in body:
            source[key] = body[key]

    # Update sub-configs (feeds, routes, etc.)
    for key in ("feeds", "routes", "subreddits", "categories", "languages", "queries"):
        if key in body:
            source[key] = body[key]

    sources[name] = source
    set_setting("sources", sources)
    return {"status": "updated"}


@app.get("/api/settings/keys")
async def get_keys(request: Request) -> list[dict]:
    """Get API key configuration status (masked values)."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    import os
    result = []
    for env_key, display_name in _API_KEY_MAP.items():
        raw_value = os.environ.get(env_key, "")
        # Also check settings table for overrides
        settings_value = get_setting(f"key:{env_key}", "")
        value = settings_value or raw_value
        result.append({
            "key": env_key,
            "name": display_name,
            "configured": bool(value),
            "masked": _mask_value(value) if value else "",
        })
    return result


@app.put("/api/settings/keys")
async def update_keys(request: Request, body: dict) -> dict[str, str]:
    """Update API keys. Keys are stored in the settings table."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    for env_key, value in body.items():
        if env_key in _API_KEY_MAP and value:
            set_setting(f"key:{env_key}", value)
    return {"status": "updated"}


@app.post("/api/settings/sources/{name}/test")
async def test_source(name: str, request: Request) -> dict:
    """Test a data source by running a quick collect."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    sources = get_setting("sources", {})
    if name not in sources:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")

    # Import and run the collector
    from src.main import COLLECTOR_REGISTRY, _import_collector

    if name not in COLLECTOR_REGISTRY:
        raise HTTPException(status_code=400, detail=f"No collector registered for '{name}'")

    module_path, class_name = COLLECTOR_REGISTRY[name]
    try:
        collector_cls = _import_collector(module_path, class_name)
        config = get_effective_config()
        collector = collector_cls(config)
        items = await collector.collect()
        await collector.close()
        return {
            "status": "ok",
            "source": name,
            "items_collected": len(items),
            "sample": [{"title": item.title[:50], "url": item.url} for item in items[:3]],
        }
    except Exception as exc:
        logger.error("Source test failed for %s: %s", name, exc, exc_info=True)
        return {
            "status": "error",
            "source": name,
            "error": str(exc),
        }
