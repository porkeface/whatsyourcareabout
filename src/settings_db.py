"""Persistent settings storage using SQLite.

Provides runtime configuration management separate from config.yaml.
Config.yaml serves as defaults; settings table stores user overrides.
"""

from __future__ import annotations

import json
import logging
import os

from src.database import get_connection

logger = logging.getLogger(__name__)

_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_settings_table() -> None:
    """Create the settings table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute(_SETTINGS_TABLE)
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default=None):
    """Read a single setting by key. Returns parsed JSON value or default."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])
    except Exception:
        logger.error("Failed to read setting: %s", key, exc_info=True)
        return default
    finally:
        conn.close()


def set_setting(key: str, value) -> bool:
    """Write a single setting. Value is JSON-serialized. Returns True on success, False on failure."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()
        logger.debug("Setting updated: %s", key)
        return True
    except Exception:
        logger.error("Failed to write setting: %s", key, exc_info=True)
        return False
    finally:
        conn.close()


def get_all_settings() -> dict:
    """Read all settings as a dict."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}
    except Exception:
        logger.error("Failed to read all settings", exc_info=True)
        return {}
    finally:
        conn.close()


def delete_setting(key: str) -> None:
    """Delete a single setting."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()
    except Exception:
        logger.error("Failed to delete setting: %s", key, exc_info=True)
    finally:
        conn.close()


def init_settings_from_config(config: dict) -> None:
    """Initialize settings table from config.yaml defaults.

    Only writes keys that don't already exist in the settings table,
    so user overrides are preserved.
    """
    init_settings_table()

    existing = get_all_settings()

    # Sources configuration
    sources = config.get("sources", {})
    if "sources" not in existing:
        set_setting("sources", sources)
    else:
        # Merge: preserve user overrides, add new sources from config
        stored = existing["sources"]
        for name, cfg in sources.items():
            if name not in stored:
                stored[name] = cfg
        set_setting("sources", stored)

    # AI summary config
    if "ai_summary" not in existing:
        set_setting("ai_summary", config.get("ai_summary", {}))

    # Processing config
    if "processing" not in existing:
        set_setting("processing", config.get("processing", {}))

    # Proxy
    if "proxy" not in existing:
        set_setting("proxy", config.get("proxy", ""))

    logger.info("Settings initialized from config")


def get_effective_config() -> dict:
    """Build the effective config by merging settings overrides with defaults.

    Returns a config dict suitable for passing to run_daily_digest().
    """
    from src.config import load_config

    config = load_config()

    # Deep-merge sources from settings into config sources
    sources = get_setting("sources")
    if sources:
        for name, cfg in sources.items():
            config["sources"][name] = cfg

    # Override ai_summary from settings
    ai_summary = get_setting("ai_summary")
    if ai_summary:
        config["ai_summary"] = ai_summary

    # Override processing from settings
    processing = get_setting("processing")
    if processing:
        config["processing"] = processing

    # Override proxy from settings
    proxy = get_setting("proxy")
    if proxy is not None:
        config["proxy"] = proxy

    # Inject API keys from settings into environment variables
    for key_name in [
        "MIMO_API_KEY",
        "NEWSAPI_KEY",
        "FINNHUB_KEY",
        "DAILYHOT_API_URL",
        "HTTPS_PROXY",
    ]:
        val = get_setting(f"key:{key_name}")
        if val:
            os.environ[key_name] = val

    return config
