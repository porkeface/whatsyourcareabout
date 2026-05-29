import logging
from datetime import datetime, timezone

import feedparser

from src.models import Item
from src.processing.cleaner import clean_text
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("rss", {})
        self._max_items: int = self._source_config.get("max_items", 20)
        self._feeds: list[dict] = self._source_config.get("feeds", [])

    def source_name(self) -> str:
        return "rss"

    def domain(self) -> str:
        return "general"

    async def collect(self) -> list[Item]:
        logger.info("Collecting RSS feeds: %d configured", len(self._feeds))
        all_items: list[Item] = []

        for feed_config in self._feeds:
            # Skip disabled feeds (enabled defaults to True)
            if feed_config.get("enabled") is False:
                logger.debug("Skipping disabled feed: %s", feed_config.get("name"))
                continue

            name = feed_config.get("name", "unknown")
            url = feed_config.get("url", "")
            domain = feed_config.get("domain", "general")

            if not url:
                logger.warning("RSS feed '%s' has no URL, skipping", name)
                continue

            try:
                items = await self._fetch_feed(name, url, domain)
                all_items.extend(items)
            except Exception:
                logger.error("Failed to collect RSS feed '%s'", name, exc_info=True)

        collected = all_items[: self._max_items]
        logger.info("Collected %d RSS items total", len(collected))
        return collected

    async def _fetch_feed(
        self, name: str, url: str, domain: str
    ) -> list[Item]:
        try:
            text = await self._fetch_text(url)
        except Exception:
            logger.error("Failed to fetch RSS feed '%s' from %s", name, url)
            return []

        try:
            feed = feedparser.parse(text)
        except Exception:
            logger.error("Failed to parse RSS feed '%s'", name)
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
                    published_at = self._parse_date(date_str)
                    if published_at is not None:
                        break

            if not title or not link:
                continue

            items.append(
                Item(
                    title=title,
                    url=link,
                    source=f"rss:{name}",
                    domain=domain,
                    raw_text=clean_text(summary, max_len=500),
                    published_at=published_at,
                )
            )

        logger.debug("Collected %d items from RSS feed '%s'", len(items), name)
        return items

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
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

        from src.utils import parse_date_flexible
        return parse_date_flexible(date_str)

        return None
