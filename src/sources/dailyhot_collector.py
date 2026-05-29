"""Collector for DailyHotApi (https://github.com/imsyy/DailyHotApi).

Fetches hot/trending content from Chinese social media platforms
(Bilibili, Weibo, Douyin, Zhihu, Baidu, Toutiao, etc.) via a
self-hosted DailyHotApi instance (e.g. on Vercel).

API response format:
    {
        "code": 200,
        "data": [
            {
                "id": "unique_id",
                "title": "title",
                "desc": "description",
                "hot": 1234567,
                "timestamp": 1716960000,
                "url": "https://...",
                "mobileUrl": "https://..."
            }
        ]
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)


class DailyHotCollector(BaseCollector):
    """Collect trending content from DailyHotApi instance."""

    def __init__(self, config: dict):
        super().__init__(config)
        source_cfg = config.get("sources", {}).get("dailyhot", {})
        self._base_url = source_cfg.get("base_url", "").rstrip("/")
        self._routes: list[dict] = source_cfg.get("routes", [])
        self._max_items: int = source_cfg.get("max_items", 30)

    async def collect(self) -> list[Item]:
        if not self._base_url:
            logger.warning("DailyHotApi base_url not configured, skipping")
            return []

        all_items: list[Item] = []

        for route in self._routes:
            # Skip disabled routes (enabled defaults to True)
            if route.get("enabled") is False:
                logger.debug("Skipping disabled route: %s", route.get("name"))
                continue

            name = route.get("name", "unknown")
            path = route.get("path", "")
            domain = route.get("domain", "social")

            items = await self._fetch_route(name, path, domain)
            all_items.extend(items)

        # Cap total items
        if len(all_items) > self._max_items:
            all_items = all_items[: self._max_items]

        logger.info("DailyHotApi collected %d items total", len(all_items))
        return all_items

    async def _fetch_route(
        self, name: str, path: str, domain: str
    ) -> list[Item]:
        """Fetch and parse a single DailyHotApi route."""
        url = f"{self._base_url}{path}"
        try:
            data = await self._fetch_json(url)
        except Exception:
            logger.warning("Failed to fetch DailyHotApi route '%s': %s", name, url, exc_info=True)
            return []

        if not data or data.get("code") != 200:
            logger.warning("DailyHotApi route '%s' returned non-200: %s", name, data)
            return []

        entries = data.get("data", [])
        if not entries:
            logger.debug("DailyHotApi route '%s' returned no entries", name)
            return []

        items: list[Item] = []
        for entry in entries:
            title = (entry.get("title") or "").strip()
            entry_url = entry.get("url") or entry.get("mobileUrl") or ""
            if not title or not entry_url:
                continue

            # Parse timestamp (seconds since epoch)
            published_at = None
            ts = entry.get("timestamp")
            if ts:
                try:
                    published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    pass

            # Hot score (may be string or int)
            hot = entry.get("hot", 0)
            try:
                score = float(hot)
            except (ValueError, TypeError):
                score = 0.0

            items.append(
                Item(
                    title=title,
                    url=entry_url,
                    source=f"dailyhot:{name}",
                    domain=domain,
                    score=score,
                    raw_text=(entry.get("desc") or "").strip(),
                    published_at=published_at,
                )
            )

        logger.debug("DailyHotApi route '%s': %d items", name, len(items))
        return items

    def source_name(self) -> str:
        return "dailyhot"

    def domain(self) -> str:
        return "social"
