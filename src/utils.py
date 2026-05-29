"""Shared utility functions for the WYCA project."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def parse_date_flexible(value: str | None) -> datetime | None:
    """Parse a date string in multiple common formats.

    Handles ISO 8601 variants, RSS date formats, and common patterns.
    Returns timezone-aware datetime (defaults to UTC if no tz info).
    Returns None if parsing fails.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    # Strip common suffixes that confuse strptime
    cleaned = value.strip()
    if cleaned.endswith(" GMT"):
        cleaned = cleaned[:-4] + "+0000"
    if cleaned.endswith(" UTC"):
        cleaned = cleaned[:-4] + "+0000"

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822 (RSS)
        "%a, %d %b %Y %H:%M:%S %Z",  # RFC 2822 with timezone name
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    logger.debug("Could not parse date string: %s", value)
    return None
