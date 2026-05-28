"""RSSHub collector for the daily hot topics aggregator.

Fetches RSS feeds from configurable RSSHub instances and routes.
RSSHub turns any website into an RSS feed, providing a unified
interface to diverse content sources.
"""

import logging
from datetime import datetime, timezone

import feedparser

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

__all__ = ["RSSHubCollector"]

_DEFAULT_BASE_URL = "https://rsshub.app"
_DEFAULT_MAX_ITEMS = 20


class RSSHubCollector(BaseCollector):
    """Collect items from RSSHub routes.

    Configuration (under ``config["sources"]["rsshub"]``):

    - ``base_url``: RSSHub instance URL (default ``"https://rsshub.app"``).
    - ``routes``: list of dicts, each with keys ``name``, ``path``,
      and ``domain``.
    - ``max_items``: maximum items to return overall (default ``20``).
    """

    def __init__(self, config: dict):
        super().__init__(config)
        rsshub_cfg = config.get("sources", {}).get("rsshub", {})
        self._base_url: str = rsshub_cfg.get("base_url", _DEFAULT_BASE_URL).rstrip("/")
        self._max_items: int = rsshub_cfg.get("max_items", _DEFAULT_MAX_ITEMS)
        self._routes: list[dict] = rsshub_cfg.get("routes", [])

    def source_name(self) -> str:
        return "rsshub"

    def domain(self) -> str:
        return "general"

    async def collect(self) -> list[Item]:
        """Fetch all configured RSSHub routes and return aggregated items."""
        logger.info("Collecting RSSHub routes: %d configured", len(self._routes))
        all_items: list[Item] = []

        for route in self._routes:
            name = route.get("name", "unknown")
            path = route.get("path", "")
            route_domain = route.get("domain", "general")

            if not path:
                logger.warning("RSSHub route '%s' has no path, skipping", name)
                continue

            url = f"{self._base_url}{path}"
            try:
                items = await self._fetch_route(name, url, route_domain)
                all_items.extend(items)
            except Exception:
                logger.error(
                    "Failed to collect RSSHub route '%s' from %s",
                    name,
                    url,
                    exc_info=True,
                )

        collected = all_items[: self._max_items]
        logger.info("Collected %d RSSHub items total", len(collected))
        return collected

    async def _fetch_route(
        self, name: str, url: str, domain: str
    ) -> list[Item]:
        """Fetch and parse a single RSSHub route.

        Returns an empty list (with a warning) if the instance is down or
        the feed cannot be parsed.
        """
        try:
            text = await self._fetch_text(url)
        except Exception:
            logger.warning(
                "RSSHub instance unreachable for route '%s' at %s, skipping",
                name,
                url,
            )
            return []

        try:
            feed = feedparser.parse(text)
        except Exception:
            logger.warning("Failed to parse RSSHub feed for route '%s'", name)
            return []

        # Detect RSSHub error responses (returns HTML error page instead of XML)
        if feed.bozo and not feed.entries:
            logger.warning(
                "RSSHub feed for route '%s' returned no entries (instance may be down)",
                name,
            )
            return []

        items: list[Item] = []

        for entry in feed.entries:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")

            published_at = None
            for date_attr in ("published", "updated", "created"):
                date_str = getattr(entry, date_attr, None)
                if date_str:
                    published_at = _parse_date(date_str)
                    if published_at is not None:
                        break

            if not title or not link:
                continue

            items.append(
                Item(
                    title=title,
                    url=link,
                    source=f"rsshub:{name}",
                    domain=domain,
                    raw_text=summary,
                    published_at=published_at,
                )
            )

        logger.debug("Collected %d items from RSSHub route '%s'", len(items), name)
        return items


def _parse_date(date_str: str) -> datetime | None:
    """Best-effort date parsing, mirroring RSSCollector._parse_date."""
    try:
        parsed = feedparser.parse(date_str)
        if parsed.get("updated_parsed"):
            from time import mktime

            return datetime.fromtimestamp(
                mktime(parsed["updated_parsed"]), tz=timezone.utc
            )
        if parsed.get("published_parsed"):
            from time import mktime

            return datetime.fromtimestamp(
                mktime(parsed["published_parsed"]), tz=timezone.utc
            )
    except Exception:
        pass

    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None
